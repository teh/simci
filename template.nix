with (import <nixpkgs> {}).pkgs;
dockerTools.buildLayeredImage {
  name = "hi";
  contents = [ hello ];
}
