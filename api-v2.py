"""
See https://docs.docker.com/registry/spec/api/#overview
and https://docs.docker.com/registry/spec/manifest-v2-2/#example-manifest-list
"""
import flask
import pathlib
import json
import subprocess
import hashlib

app = flask.Flask(__name__)


EMPTY_MANIFESTS = {
    "schemaVersion": 2,
    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
}


CONFIG_DB = dict()

def _layer_from_path(path: pathlib.Path):
    "Translate the output from `mkManyPureLayers` to what docker expects."
    layer = path.joinpath('layer.tar')
    size = layer.stat().st_size
    meta = json.loads(path.joinpath('json').read_text())

    gzip_bytes = subprocess.check_output(['gzip', '--fast'], stdin=layer.open())
    digest = 'sha256:' + hashlib.sha256(gzip_bytes).hexdigest()
    layer_sha256 = 'sha256:' + hashlib.sha256(layer.read_bytes()).hexdigest()

    return {
        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "size": size,
        "digest": digest, # compressed
        "layer_sha256": layer_sha256, # uncompressed
    }


def _build_layers():
    # TODO(tom): need to connect entry point to actual nix (see template.nix
    # for how I generated the path below)
    entrypoint = pathlib.Path('/nix/store/3vi7bz32hdfh26k07ipy96k1ar99lw0q-hi-granular-docker-layers/')
    entrypoint = pathlib.Path('./entrypoint')
    for x in sorted(entrypoint.glob('*'), reverse=True):
        yield _layer_from_path(x)


@app.route('/v2/')
def v2():
    # > When a 200 OK or 401 Unauthorized response is returned, the
    # > “Docker-Distribution-API-Version” header should be set to “registry/2.0”
    response = app.response_class("")
    print(flask.request.headers)
    response.headers['Docker-Distribution-API-Version'] = 'registry/2.0'
    return response


@app.route('/v2/<path:name>/blobs/<string:reference>')
def blobs(name, reference):
    if reference in CONFIG_DB:
        return app.response_class(
            response=CONFIG_DB[reference],
            mimetype='application/vnd.docker.container.image.v1+json',
        )


    entrypoint = pathlib.Path('/nix/store/3vi7bz32hdfh26k07ipy96k1ar99lw0q-hi-granular-docker-layers/')
    entrypoint = pathlib.Path('./entrypoint')
    for x in sorted(entrypoint.glob('*'), reverse=True):
        layer = _layer_from_path(x)
        if layer['digest'] == reference:
            return subprocess.check_output(['gzip', '--fast'], stdin=x.joinpath('layer.tar').open())
    flask.abort(404)


@app.route('/v2/<path:name>/manifests/<string:reference>')
def manifests(name, reference):
    m = EMPTY_MANIFESTS
    m['layers'] = list(_build_layers())

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

    CONFIG_DB[digest] = json_bytes

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
