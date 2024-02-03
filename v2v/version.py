from pbr import version as pbr_version

VENDOR = "Aiops"
PRODUCT = "easy-v2v"

loaded = False
version_info = pbr_version.VersionInfo('easy-v2v')
version_string = version_info.version_string
