with (import <nixpkgs> {}).pkgs;
let
diskcache = python3Packages.buildPythonPackage rec {
  pname = "diskcache";
  version = "3.0.6";
  src = python3Packages.fetchPypi {
    inherit pname version;
    sha256 = "1wyb4hks977i2c134dnxdsgq0wgwk1gb3d5yk3zhgjidc6f1gw0m";
  };
  doCheck = false;
};
p3 = python3Packages.python.withPackages (ps: [ ps.flask diskcache ]);
in mkShell {
  buildInputs = [ p3 pigz ];
}
