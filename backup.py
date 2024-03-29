#!/usr/bin/env python3
import sys, os, argparse, pathlib, yaml, sh

def usage():
	sys.stderr.write(
	"\n"
	"You may use command-line arguments, a config file (YAML format)\n"
	"or environment variables to configure this program.\n"
	"\n"
	"Precedence:\n"
	"\t1. Command-line overrides all others.\n"
	"\t2. Config file (overridden by above)\n"
	"\t3. Environment variables (overridden by above)\n"
	"\t4. Defaults values (overridden by above)\n"
	"\n"
	"================================================================\n"
	"These are valid command line arguments:\n"
	"================================================================\n"
	"\n"
	"These are *only* found via command-line arguments:\n"
	"--full\t\t\t(Default: False) Perform a full backup.\n"
	"--args\t\t\t(Default None) Extra args to duplicity.\n"
	"--config\t\t(Default: backup.yml) Config file\n"
	"\t\t\tlocation.\n"
	"\n"
	"These command-line arguments override other forms of config:\n"
	"--gpg-public\t\tGPG key used to encrypt/sign backups.\n"
	"--log-dir\t\tDirectory containing logs.\n"
	"--log-file\t\tName of log file.\n"
	"--source-basedir\tBase/root directory on the source\n"
	"\t\t\tfilesystem. --directories are inside of\n"
	"\t\t\tthis location.\n"
	"--dest-basedir\t\tBase/root directory on the destination\n"
	"\t\t\tfilesystem. --directories will go to\n"
	"\t\t\tthis location.\n"
	"--dest-proto\t\tProtocol used to backup.\n"
	"--dest-user\t\tUser on the destination host to\n"
	"\t\t\tconnect as.\n"
	"--dest-host\t\tThe hostname or IP of the\n"
	"\t\t\tdestination host.\n"
	"--dest-port\t\tPort on the destination host to\n"
	"\t\t\tconnect on.\n"
	"--dest-uri\t\tOverride *connection* URI. Does not\n"
	"\t\t\tchange other `dest` values.\n"
	"--directories\t\tSpace-separated list of\n"
	"\t\t\tdirectories to backup.\n"
	"\n"
	"================================================================\n"
	"These fields are valid inside a backup.yml config file:\n"
	"================================================================\n\n"
	"---\n"
	f"{yaml.safe_dump(getDefaults())}\n"
	"================================================================\n"
	"Please fill out a valid config file and try again.\n"
	"Exiting.\n"
	"================================================================\n"
	"\n"
	)

def getDefaults():
	return {
		"gpg": {
			"public": ""
		},
		"log": {
			"dir": "/var/log",
			"file": "backup.log"
		},
		"source": {
			"baseDir": "/mnt/mydata"
		},
		"dest": {
			"baseDir": "/mnt/backup/mydata",
			"proto": "rsync",
			"user": "root",
			"host": "offsite",
			"port": 22,
			"uri": ""
		},
		"directories": [
			"Code",
			"Documents",
			"Movies",
			"Music",
			"Pictures"
		],
		"full": False,
		"args": [],
		"config": "/opt/backup.yml"
	}

def getEnv():
	return {
		"gpg": {
			"public": str(os.environ.get("backup_gpg_public", ""))
		},
		"log": {
			"dir": str(os.environ.get("backup_log_dir", "")),
			"file": str(os.environ.get("backup_log_file", ""))
		},
		"source": {
			"baseDir": str(os.environ.get("backup_source_baseDir", ""))
		},
		"dest": {
			"baseDir": str(os.environ.get("backup_dest_baseDir", "")),
			"proto": str(os.environ.get("backup_dest_proto", "")),
			"user": str(os.environ.get("backup_dest_user", "")),
			"host": str(os.environ.get("backup_dest_host", "")),
			"port": int(os.environ.get("backup_dest_port", -1)),
			"uri": str(os.environ.get("backup_dest_uri", ""))
		},
		"directories": strToList(os.environ.get("backup_directories", ""), splitter=","),
		"full": bool(os.environ.get("backup_full", False)), # too lazy to get around not setting a default here
		"args": strToList(os.environ.get("backup_args", ""), splitter=" "),
		"config": ""
	}

def getArgs():
	parser = argparse.ArgumentParser(description="Backup stuff using duplicity.")
	# ones that control others
	parser.add_argument("--full", action="store_true", required=False, default=False, help="(Default: False) Perform a full backup.") # too lazy to get around not setting a default here
	parser.add_argument("--args", type=str, required=False, default="", help="(Default None) Extra args to duplicity.")
	parser.add_argument("--config", type=str, required=False, default="", help="(Default: /opt/backup.yml) Config file location.")

	# optional overrides
	parser.add_argument("--gpg-public", type=str, required=False, default="", help="GPG key used to encrypt/sign backups.")
	parser.add_argument("--log-dir", type=str, required=False, default="", help="Directory containing logs.")
	parser.add_argument("--log-file", type=str, required=False, default="", help="Name of log file.")
	parser.add_argument("--source-basedir", type=str, required=False, default="", help="Base/root directory on the source filesystem. --directories are inside of this location.")
	parser.add_argument("--dest-basedir", type=str, required=False, default="", help="Base/root directory on the destination filesystem. --directories will go to this location.")
	parser.add_argument("--dest-proto", type=str, required=False, default="", help="Protocol used to backup.")
	parser.add_argument("--dest-user", type=str, required=False, default="", help="User on the destination host to connect as.")
	parser.add_argument("--dest-host", type=str, required=False, default="", help="The hostname or IP of the destination host.")
	parser.add_argument("--dest-port", type=int, required=False, default=-1, help="Port on the destination host to connect on.")
	parser.add_argument("--dest-uri", type=str, required=False, default="", help="Override *connection* URI. Does not change other `dest` values.")
	parser.add_argument("--directories", type=str, required=False, default="", help="Space-separated list of directories to backup.")

	args = parser.parse_args()

	return {
		"gpg": {
			"public": args.gpg_public
		},
		"log": {
			"dir": args.log_dir,
			"file": args.log_file
		},
		"source": {
			"baseDir": args.source_basedir
		},
		"dest": {
			"baseDir": args.dest_basedir,
			"proto": args.dest_proto,
			"user": args.dest_user,
			"host": args.dest_host,
			"port": args.dest_port
		},
		"directories": strToList(args.directories, splitter=","),
		"full": args.full,
		"args": strToList(args.args, splitter=" "),
		"config": args.config
	}

def getConfigFile(file):
	if not pathlib.Path(file).exists():
		return {}

	with open(file, "r") as f:
		_config = yaml.safe_load(f)

	if _config == None:
		_config = {}

	return _config

def strToList(string, splitter=","):
	_list = str(string).split(splitter)
	if _list == [""]:
		_list = []

	return list(_list)

def merge(overlay={}, config={}):
	config = config.copy()
	for _key, _value in overlay.items(): # loop through each key/value pair
		if (_key in config) and isinstance(_value, dict): # detect when we need to recurse
			config[_key] = merge(_value, config[_key]) # recurse
		else: # _key is not in output
			if _value == "" or _value == -1 or _value == [] or _value == None:
				continue
			config[_key] = _value # add key/value pair

	return config # give back the merged dict

# precedence:
# 1. args (override all)
# 2. config file (overridden by above)
# 3. environment variables (overridden by above)
# 4. default values (overridden by above)

args = getArgs() # we always need args

config = getDefaults() # start with defaults
config = merge(getEnv(), config) # overlay env

if not args["config"] == "": # we need to read args early to see which config to load next
	config['config'] = args["config"] # use what we found since it isn't a zero-length string

config = merge(getConfigFile(config['config']), config) # overlay config file
config = merge(args, config) # overlay args

if config["gpg"]["public"] == "":
	usage()
	sys.stderr.write("You MUST set `gpg.public` to a valid GPG public key. Use gpg --list-keys to see what's available.\n")
	sys.exit(1)

if not pathlib.Path(config["log"]["dir"]).exists():
	usage()
	sys.stdout.write(f"Cannot locate `log.dir` {config['log']['dir']} on the source machine.\n")
	sys.exit(1)

logDir = f"{config['log']['dir']}/{config['log']['file']}"

if config["dest"]["uri"] == "":
	config["dest"]["uri"] = f"{config['dest']['proto']}:/{config['dest']['user']}@{config['dest']['host']}:{config['dest']['port']}/"

if len(config["directories"]) <= 0:
	usage()
	sys.stdout.write("Nothing to do.\n")
	sys.exit(0)

for item in config["directories"]:
	duplicitySource = f"{config['source']['baseDir']}/{item}"
	duplicityDest = f"{config['dest']['baseDir']}/{item}"

	if not pathlib.Path(duplicitySource):
		sys.stderr.write(f"Couldn't find source {duplicitySource}. Skipping.\n")
		continue

	ssh = sh.ssh.bake(p=config["dest"]["port"], l=config["dest"]["user"])
	try:
		ssh("-o", "UpdateHostKeys=yes", "-o", "StrictHostKeyChecking=accept-new", config["dest"]["host"], "mkdir", "-p", f"{duplicityDest}")
	except Exception as e:
		sys.stderr.write(f"You must setup and test SSH ahead of time. See below for errors:\n{e}\n")
		sys.exit(1)

	duplicity_args = []
	if config["full"]:
		duplicity_args.append("full")
	if config["args"]:
		if type(config["args"]) == list: # no nested lists
			duplicity_args.extend(config["args"]) # no nested lists
		else:
			duplicity_args.append(config["args"])
	duplicity_args.append(duplicitySource)
	duplicity_args.append(f"{config['dest']['uri']}{duplicityDest}")

	prettyArgs = ' '.join(duplicity_args)
	out = f"Running: duplicity --encrypt-key {config['gpg']['public']} {prettyArgs}\n"
	equals = ""
	for i in out:
		equals = equals + "="
	equals = equals + "\n"
	sys.stdout.write(
		equals +
		out +
		equals
)

	duplicity = sh.duplicity.bake(encrypt_key=config["gpg"]["public"])
	_backup = duplicity(duplicity_args)
	sys.stdout.write(f"{_backup}\n")
