#!/usr/bin/env python3
import sys
import os
import pathlib
import sh
from jsonargparse import ArgumentParser, ActionConfigFile
from typing import List

SSH_BASED_PROTOS = ['ssh', 'rsync']


class ConfigParser():
    def __init__(self):
        parser = ArgumentParser(default_config_files=['/opt/backup.yml'], env_prefix="DUPBACK", default_env=True)

        parser.add_argument("--command", required=False, default="", choices=[
                'full', 'verify', 'collection-status', 'list-current-files', 
                'restore', 'remove-older-than', 'remove-all-but-n-full',
                'cleanup', 'replicate'
            ], 
                            help="Set duplicity command e.g. full, restore, remove-all-but-n-full") 
        parser.add_argument("--args", type=List[str], required=False, default=[], help="(Default None) Extra args to duplicity.")
        parser.add_argument("--config", action=ActionConfigFile)

        # optional overrides
        parser.add_argument("--gpg.fingerprint", type=str, required=True, default="", help="Fingerprint of GPG key used to encrypt/sign backups.")
        parser.add_argument("--gpg.public-key-pem", type=str, required=False, help="Public key in pem format.")
        parser.add_argument("--gpg.private-key-pem", type=str, required=False, help="Private key in pem format (password protected).")
        parser.add_argument("--log.dir", type=str, required=False, default="", help="Directory containing logs.")
        parser.add_argument("--log.file", type=str, required=False, default="", help="Name of log file.")
        parser.add_argument("--source.baseDir", type=str, required=False, default="", help="Base/root directory on the source filesystem. --directories are inside of this location.")
        parser.add_argument("--dest.baseDir", type=str, required=True, help="Base/root directory on the destination filesystem. --directories will go to this location.")
        parser.add_argument("--dest.proto", type=str, required=False, help="Protocol used to backup.")
        parser.add_argument("--dest.user", type=str, required=False, help="User on the destination host to connect as.")
        parser.add_argument("--dest.host", type=str, required=False, help="The hostname or IP of the destination host.")
        parser.add_argument("--dest.port", type=int, required=False, help="Port on the destination host to connect on.")
        parser.add_argument("--dest.uri", type=str, required=False, default="", help="Override *connection* URI. Does not change other `dest` values.")
        parser.add_argument("--directories", type=List[str], required=False, default=[], help="list of directories to backup. in json syntax '[dirA, dirB]'")
        parser.add_argument("--all-subdirectories", type=bool, default=False, help="all 1st level subdirectories of `source-basedir` get separatly backuped. `directories are ignored`")
        parser.add_argument("--no-default-config", action="store_true", required=False, default=False, help="do not load default config values from code and files.")
        self.parser = parser

    def __call__(self):
        cfg_d = self.parser.parse_args()
        if cfg_d.no_default_config:
            cfg_d = self.parser.parse_args(defaults=False)
        return cfg_d

    def usage(self):
        print(self.parser.print_help())

# precedence:
# 1. args (override all)
# 2. config file (overridden by above)
# 3. environment variables (overridden by above)
# 4. default values (overridden by above)


cp = ConfigParser()
config = cp()

if config.gpg.fingerprint == "":
    cp.usage()
    sys.stderr.write(
        "You MUST set `gpg.fingerprint` to a valid GPG public key. Use gpg --list-keys to see what's available.\n")
    sys.exit(1)
else:
    try:
        public_key_available = config.gpg.fingerprint in sh.gpg(
            "--list-keys", "--with-colons", "--with-fingerprint", config.gpg.fingerprint)
    except sh.ErrorReturnCode as sh_err:
        if b"No public key" in sh_err.stderr:
            public_key_available = False
        else:
            raise sh_err

    if not public_key_available:
        print(
            f'No key found with fingerprint {config.gpg.fingerprint}, try import')
        if len(config.gpg.public_key_pem) > 0:
            try:
                sh.gpg("--import", _in=config.gpg.public_key_pem)
                sh.gpg("--import-ownertrust",
                       _in=f'{config.gpg.fingerprint}:6:\n')
                if not config.gpg.fingerprint in sh.gpg("--list-keys", "--with-colon", "--with-fingerprint"):
                    sys.stderr.write(
                        f'Wrong key was imported, check fingerprint.\n')
                    print(sh.gpg("--list-keys"))
                    print(sh.gpg("--export-ownertrust"))
                    sys.exit(1)
                print("Public Key import successful.")
            except sh.ErrorReturnCode as sh_err:
                sys.stderr.write(f"""Can't import and trust public key: 
                     Command: {sh_err.full_cmd}
                     StdOut: {sh_err.stdout}
                     StrErr: {sh_err.stderr}\n""")
                sys.exit(1)
        else:
            sys.stderr.write(
                f'No public key to import set "gpg.public_key_pem". Abort.\n')
            sys.exit(1)

    if config.gpg.private_key_pem:
        try:
            private_key_imported = config.gpg.fingerprint in sh.gpg(
                "--list-secret-keys", "--with-colons", "--with-fingerprint", config.gpg.fingerprint)
        except sh.ErrorReturnCode as sh_err:
            if b"No secret key" in sh_err.stderr:
                private_key_imported = False
            else:
                raise sh_err

        if not private_key_imported:
            try:
                sh.gpg("--import", "--batch", "--with-colons", _in=config.gpg.private_key_pem)
                if not config.gpg.fingerprint in sh.gpg("--list-secret-keys", "--with-colon", "--with-fingerprint"):
                    sys.stderr.write(
                        f'Wrong key was imported, check fingerprint.\n')
                    print(sh.gpg("--list-secret-keys"))
                    if not os.getenv("PASSPHRASE"): print("If your private key is encrypted, ensure env var 'PASSPHRASE' is set and valid.")
                    sys.exit(1)
                print("Privat Key import successful.")
            except sh.ErrorReturnCode as sh_err:
                sys.stderr.write(f"""Can't import privat key: 
                     Command: {sh_err.full_cmd}
                     StdOut: {sh_err.stdout}
                     StrErr: {sh_err.stderr}\n""")
                sys.exit(1)

if not pathlib.Path(config.log.dir).exists():
    cp.usage()
    sys.stdout.write(
        f"Cannot locate `log.dir` {config.log.dir} on the source machine.\n")
    sys.exit(1)

logDir = f"{config.log.dir}/{config.log.file}"

if config.dest.uri == "":
    config.dest.uri = f"{config.dest.proto}:/{config.dest.user}@{config.dest.host}:{config.dest.port}/"

if config.all_subdirectories:
    # replacing directories with all subdirectories of source base dir
    rootdir = f"{config.source.baseDir}"
    if pathlib.Path(rootdir):
        subdirs = [x.name for x in os.scandir(
            rootdir) if x.is_dir() and not x.name.startswith(('.', '@'))]
        config.update(subdirs, "directories")

if len(config.directories) <= 0:
    cp.usage()
    sys.stdout.write("Nothing to do.\n")
    sys.exit(0)

for item in config.directories:
    duplicitySource = os.path.join(config.source.baseDir, item)
    duplicityDest = f"{config.dest.uri}{os.path.join(config.dest.baseDir, item)}"

    if not pathlib.Path(duplicitySource):
        sys.stderr.write(
            f"Couldn't find source {duplicitySource}. Skipping.\n")
        continue

    # Run some preps if SSH based connection
    proto = config.dest.uri.partition(":")[0]
    if proto in SSH_BASED_PROTOS:
        ssh = sh.ssh.bake(p=config.dest.port, l=config.dest.user)
        try:
            ssh("-o", "UpdateHostKeys=yes", "-o", "StrictHostKeyChecking=accept-new",
                config.dest.host, "mkdir", "-p", f"{duplicityDest}")
        except Exception as e:
            sys.stderr.write(
                f"You must setup and test SSH ahead of time. See below for errors:\n{e}\n")
            sys.exit(1)

    duplicity_args = []
    skip_dest = skip_source = False
    if "full" == config.command:
        duplicity_args.append(config.command)
    elif "restore" == config.command or "verify" in config.command:
        duplicityDest, duplicitySource = duplicitySource, duplicityDest
        duplicity_args.append(config.command)
    elif any([x in config.command for x in ["collection-status", "remove", "cleanup", "list-current-files"]]):
        skip_source = True
        duplicity_args.append(config.command)
    if config.args:
        if type(config.args) == list:  # no nested lists
            duplicity_args.extend(config.args)  # no nested lists
        else:
            duplicity_args.append(config.args)
    if not skip_source: duplicity_args.append(duplicitySource) 
    if not skip_dest: duplicity_args.append(duplicityDest) 

    prettyArgs = ' '.join(duplicity_args)
    out = f"Running: duplicity --encrypt-key {config.gpg.fingerprint} {prettyArgs}\n"
    equals = ""
    for i in out:
        equals = equals + "="
    equals = equals + "\n"
    sys.stdout.write(
        equals +
        out +
        equals
    )

    duplicity = sh.duplicity.bake(encrypt_key=config.gpg.fingerprint)
    for line in duplicity(duplicity_args, _iter=True):
        print(line, end="")
