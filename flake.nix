{
  description = "Home Assistant on Stream Deck: configured via YAML (with templates)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        python = pkgs.python312;

        # The streamdeck library is not in nixpkgs, so we build it
        streamdeck = python.pkgs.buildPythonPackage rec {
          pname = "streamdeck";
          version = "0.9.7";
          format = "setuptools";

          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-jVhuZihvjuA5rwl55JAmtFq+h/f5M68Vo44jh8HjUI4=";
          };

          propagatedBuildInputs = with python.pkgs; [
            pillow
          ];

          # Patch to find hidapi library in the Nix store
          postPatch =
            let
              hidapiLib = if pkgs.stdenv.isLinux then
                "${pkgs.hidapi}/lib/libhidapi-libusb.so"
              else if pkgs.stdenv.isDarwin then
                "${pkgs.hidapi}/lib/libhidapi.dylib"
              else
                "${pkgs.hidapi}/lib/libhidapi${pkgs.stdenv.hostPlatform.extensions.sharedLibrary}";
            in ''
              substituteInPlace src/StreamDeck/Transport/LibUSBHIDAPI.py \
                --replace-fail '"Linux": ["libhidapi-libusb.so", "libhidapi-libusb.so.0"]' '"Linux": ["${hidapiLib}", "libhidapi-libusb.so", "libhidapi-libusb.so.0"]' \
                --replace-fail '"Darwin": ["libhidapi.dylib"]' '"Darwin": ["${hidapiLib}", "libhidapi.dylib"]'
            '';

          nativeCheckInputs = with python.pkgs; [
            pytestCheckHook
          ];

          # Tests require hardware
          doCheck = false;

          pythonImportsCheck = [ "StreamDeck" ];

          meta = with pkgs.lib; {
            description = "Python library for controlling Elgato Stream Deck devices";
            homepage = "https://github.com/abcminiuser/python-elgato-streamdeck";
            license = licenses.mit;
          };
        };

        home-assistant-streamdeck-yaml = python.pkgs.buildPythonApplication {
          pname = "home-assistant-streamdeck-yaml";
          version = "0.0.0+${self.shortRev or self.dirtyShortRev or "dev"}";
          format = "pyproject";

          src = ./.;

          # Set a valid PEP 440 version for setuptools-scm
          env.SETUPTOOLS_SCM_PRETEND_VERSION = "0.0.0";

          # Remove unidep from build requirements since we specify deps manually
          postPatch = ''
            substituteInPlace pyproject.toml \
              --replace-fail ', "unidep[toml]"' "" \
              --replace-fail 'dynamic = ["version", "dependencies"]' 'dynamic = ["version"]'
          '';

          nativeBuildInputs = with python.pkgs; [
            setuptools
            setuptools-scm
            wheel
          ];

          propagatedBuildInputs = with python.pkgs; [
            streamdeck
            cairosvg
            jinja2
            lxml
            pillow
            pydantic_1  # pydantic <2
            python-dotenv
            pyyaml
            requests
            rich
            websockets
          ];

          # Runtime dependencies for cairosvg and streamdeck
          makeWrapperArgs = [
            "--prefix" "LD_LIBRARY_PATH" ":" "${pkgs.lib.makeLibraryPath [
              pkgs.hidapi
              pkgs.libusb1
            ]}"
          ];

          # Tests require Home Assistant connection and hardware
          doCheck = false;

          pythonImportsCheck = [ "home_assistant_streamdeck_yaml" ];

          meta = with pkgs.lib; {
            description = "Home Assistant on Stream Deck: configured via YAML (with templates)";
            homepage = "https://github.com/basnijholt/home-assistant-streamdeck-yaml";
            license = licenses.mit;
            mainProgram = "home-assistant-streamdeck-yaml";
          };
        };

      in
      {
        packages = {
          default = home-assistant-streamdeck-yaml;
          home-assistant-streamdeck-yaml = home-assistant-streamdeck-yaml;
        };

        apps.default = {
          type = "app";
          program = "${home-assistant-streamdeck-yaml}/bin/home-assistant-streamdeck-yaml";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            (python.withPackages (ps: with ps; [
              streamdeck
              cairosvg
              jinja2
              lxml
              pillow
              pydantic_1
              python-dotenv
              pyyaml
              requests
              rich
              websockets
              # Dev dependencies
              pytest
              pytest-asyncio
              pytest-cov
              # Docs dependencies
              pandas
              tabulate
              tqdm
              # Colormap support
              matplotlib
            ]))
            pkgs.pre-commit
            pkgs.hidapi
            pkgs.libusb1
          ];

          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [
              pkgs.hidapi
              pkgs.libusb1
            ]}:$LD_LIBRARY_PATH"
            echo "home-assistant-streamdeck-yaml development shell"
            echo "Run 'python home_assistant_streamdeck_yaml.py' to start"
          '';
        };

        # For NixOS: udev rules for Stream Deck devices
        nixosModules.default = { config, lib, pkgs, ... }: {
          options.services.home-assistant-streamdeck-yaml = {
            enable = lib.mkEnableOption "Home Assistant Stream Deck YAML service";

            configFile = lib.mkOption {
              type = lib.types.path;
              description = "Path to the configuration YAML file";
            };

            hassHost = lib.mkOption {
              type = lib.types.str;
              default = "localhost";
              description = "Home Assistant host";
            };

            hassTokenFile = lib.mkOption {
              type = lib.types.path;
              description = "Path to file containing the Home Assistant token";
            };

            protocol = lib.mkOption {
              type = lib.types.enum [ "wss" "ws" ];
              default = "wss";
              description = "WebSocket protocol to use";
            };

            user = lib.mkOption {
              type = lib.types.str;
              default = "streamdeck";
              description = "User to run the service as";
            };
          };

          config = lib.mkIf config.services.home-assistant-streamdeck-yaml.enable {
            # Udev rules for Stream Deck
            services.udev.extraRules = ''
              # Elgato Stream Deck Original
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0060", MODE="0666"
              # Elgato Stream Deck Original V2
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="006d", MODE="0666"
              # Elgato Stream Deck Mini
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0063", MODE="0666"
              # Elgato Stream Deck Mini V2
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0090", MODE="0666"
              # Elgato Stream Deck XL
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="006c", MODE="0666"
              # Elgato Stream Deck XL V2
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="008f", MODE="0666"
              # Elgato Stream Deck MK.2
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0080", MODE="0666"
              # Elgato Stream Deck Pedal
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0086", MODE="0666"
              # Elgato Stream Deck +
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0084", MODE="0666"
              # Elgato Stream Deck Neo
              SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="009a", MODE="0666"
            '';

            users.users.${config.services.home-assistant-streamdeck-yaml.user} = {
              isSystemUser = true;
              group = config.services.home-assistant-streamdeck-yaml.user;
              extraGroups = [ "plugdev" ];
            };

            users.groups.${config.services.home-assistant-streamdeck-yaml.user} = {};

            systemd.services.home-assistant-streamdeck-yaml = {
              description = "Home Assistant Stream Deck YAML";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];

              serviceConfig = {
                Type = "simple";
                User = config.services.home-assistant-streamdeck-yaml.user;
                ExecStart = ''
                  ${home-assistant-streamdeck-yaml}/bin/home-assistant-streamdeck-yaml \
                    --host ${config.services.home-assistant-streamdeck-yaml.hassHost} \
                    --token $(cat ${config.services.home-assistant-streamdeck-yaml.hassTokenFile}) \
                    --config ${config.services.home-assistant-streamdeck-yaml.configFile} \
                    --protocol ${config.services.home-assistant-streamdeck-yaml.protocol}
                '';
                Restart = "on-failure";
                RestartSec = "5s";
              };
            };
          };
        };
      }
    );
}
