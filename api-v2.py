"""
See https://docs.docker.com/registry/spec/api/#overview
and https://docs.docker.com/registry/spec/manifest-v2-2/#example-manifest-list
"""
import flask
import pathlib
import json
import subprocess
import hashlib
import diskcache

app = flask.Flask(__name__)

dcache = diskcache.FanoutCache('/tmp/simci-cache/', shards=4, timeout=2, eviction_policy='least-recently-used')

EMPTY_MANIFESTS = {
    "schemaVersion": 2,
    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
}


def _to_nix_str_list(items):
    return "[" + " ".join(f'"{x}"' for x in items) + "]"


def _get_layers(attribute_path):
    subprocess.check_output(['nix-build', 'template.nix', '--arg', 'attributepath',  _to_nix_str_list(attribute_path)])

    result = json.loads(pathlib.Path('./result').read_text())
    for x in pathlib.Path(result['layers']).glob('*'):
        yield x.resolve()

    yield pathlib.Path(result['toplayer']).resolve()


def _layer_from_path(path: pathlib.Path):
    "Translate the output from `mkManyPureLayers` to what docker expects."
    cache_key = str(path)
    if cache_key in dcache:
        return dcache[cache_key]

    layer = path.joinpath('layer.tar')
    size = layer.stat().st_size
    meta = json.loads(path.joinpath('json').read_text())

    gzip_bytes = subprocess.check_output(['pigz', '--fast'], stdin=layer.open())
    digest = 'sha256:' + hashlib.sha256(gzip_bytes).hexdigest()
    layer_sha256 = 'sha256:' + hashlib.sha256(layer.read_bytes()).hexdigest()

    dcache[digest] = gzip_bytes

    layer_meta = {
        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "size": size,
        "digest": digest, # compressed
        "layer_sha256": layer_sha256, # uncompressed
    }
    dcache[cache_key] = layer_meta
    return layer_meta


def _build_layers(attribute_path):
    # TODO(tom): need to connect entry point to actual nix (see template.nix
    # for how I generated the path below)
    for x in _get_layers(attribute_path):
        yield _layer_from_path(x)


@app.route('/v2/')
def v2():
    # > When a 200 OK or 401 Unauthorized response is returned, the
    # > “Docker-Distribution-API-Version” header should be set to “registry/2.0”
    response = app.response_class("")
    response.headers['Docker-Distribution-API-Version'] = 'registry/2.0'
    return response


@app.route('/v2/<path:name>/blobs/<string:reference>')
def blobs(name, reference):
    if reference not in dcache:
        flask.abort(404)

    return app.response_class(
        response=dcache[reference],
        mimetype='application/vnd.docker.container.image.v1+json',
    )


@app.route('/v2/<path:name>/manifests/<string:reference>')
def manifests(name, reference):
    m = EMPTY_MANIFESTS

    attribute_path = reference.split('.')

    m['layers'] = list(_build_layers(attribute_path))

    rootfs = {
        "architecture": "amd64",
        "created": "1970-01-01T00:00:01Z",
        "os": "linux",
        'rootfs': {
            'type': 'layers',
            'diff_ids': [x.pop('layer_sha256') for x in m['layers']],
        }
    }

    json_bytes = json.dumps(rootfs, indent=4).encode('utf8')
    digest = 'sha256:' + hashlib.sha256(json_bytes).hexdigest()

    m['config'] = {
        "mediaType": "application/vnd.docker.container.image.v1+json",
        "size": len(json_bytes),
        "digest": digest,
    }

    dcache[digest] = json_bytes

    print(json_bytes.decode('utf8'))
    print(json.dumps(m, indent=4))

    response = app.response_class(
        response=json.dumps(m),
        mimetype='application/vnd.docker.distribution.manifest.v2+json',
    )
    response.headers['Docker-Distribution-API-Version'] = 'registry/2.0'
    return response


def main():
    app.run()


if __name__ == '__main__':
    main()
