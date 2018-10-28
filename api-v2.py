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
    "config": {
        "mediaType": "application/vnd.docker.container.image.v1+json",
        # TODO(tom): how do we know the following two?
        "size": 2,
        "digest": "sha256:a92ea37ee34703d3d18f858f6085abf894b696dc8ba53205c657553a08d5eec3",
    },
}

def _layer_from_path(path: pathlib.Path):
    "Translate the output from `mkManyPureLayers` to what docker expects."
    layer = path.joinpath('layer.tar')
    size = layer.stat().st_size
    meta = json.loads(path.joinpath('json').read_text())

    digest = 'sha256:' + hashlib.sha256(subprocess.check_output(['gzip'], stdin=layer.open())).hexdigest()

    return {
        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "size": size,
        "digest": digest,
    }


def _build_layers():
    # TODO(tom): need to connect entry point to actual nix (see template.nix
    # for how I generated the path below)
    entrypoint = pathlib.Path('/nix/store/3vi7bz32hdfh26k07ipy96k1ar99lw0q-hi-granular-docker-layers/')
    for x in entrypoint.glob('*'):
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
    if reference == "sha256:a92ea37ee34703d3d18f858f6085abf894b696dc8ba53205c657553a08d5eec3":
        return flask.sendfile('o/a92ea37ee34703d3d18f858f6085abf894b696dc8ba53205c657553a08d5eec3.json')

    entrypoint = pathlib.Path('/nix/store/3vi7bz32hdfh26k07ipy96k1ar99lw0q-hi-granular-docker-layers/')
    for x in entrypoint.glob('*'):
        layer = _layer_from_path(x)
        if layer['digest'] == reference:
            return subprocess.check_output(['gzip'], stdin=x.joinpath('layer.tar').open())
    flask.abort(404)


@app.route('/v2/<path:name>/manifests/<string:reference>')
def manifests(name, reference):
    m = EMPTY_MANIFESTS
    m['layers'] = list(_build_layers())
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
