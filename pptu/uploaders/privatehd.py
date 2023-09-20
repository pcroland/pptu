from ._avistaznetwork import AvistaZNetworkUploader


class PrivateHDUploader(AvistaZNetworkUploader):
    name: str = "PrivateHD"
    abbrev: str = "PHD"
