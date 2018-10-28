{ attributepath ? ["hello"], tarPath }:
let
# host packages to host the mkManyPureLayers
hostPackages = (import (fetchTarball {
  url = https://github.com/NixOS/nixpkgs/archive/d9423ee4464e02fd90eb2ca6192017a00a0805bf.tar.gz;
  sha256 = "1rc8n5vmkzbaj5kf4qwaxii103pi6s27ll1n0dvcgrxiw871dysw";
}) {});
tarImport = (import (builtins.fetchTarball tarPath) {});
contents = hostPackages.lib.getAttrFromPath attributepath tarImport;
configJson = hostPackages.writeText "layers.json" (builtins.toJSON {
  architecture = "amd64";
  os = "linux";
  config = {};
});
layer1 = hostPackages.dockerTools.mkManyPureLayers {
      name = "Blarg";
      closure = contents;
      configJson = configJson;
      maxLayers = 100;
    };
custom = hostPackages.dockerTools.mkCustomisationLayer {
  name = "blarg2";
  contents = contents;
  baseJson = configJson;
};
in hostPackages.writeText "layers.json" (builtins.toJSON {
  layers = layer1;
  toplayer = custom;
})
