{ attributepath ? ["hello"] }: with (import <nixpkgs> {}).pkgs;
let
contents = lib.getAttrFromPath attributepath pkgs;
configJson = writeText "layers.json" (builtins.toJSON {
  architecture = "amd64";
  os = "linux";
  config = {};
});
layer1 = dockerTools.mkManyPureLayers {
      name = "Blarg";
      closure = contents;
      configJson = configJson;
    };
custom = dockerTools.mkCustomisationLayer {
  name = "blarg2";
  contents = contents;
  baseJson = configJson;
};
in writeText "layers.json" (builtins.toJSON {
  layers = layer1;
  toplayer = custom;
})
