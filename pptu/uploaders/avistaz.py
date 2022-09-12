from ._avistaznetwork import AvistaZNetworkUploader


class AvistaZUploader(AvistaZNetworkUploader):
    name = "AvistaZ"
    abbrev = "AvZ"

    keep_dubbed_dual_tags = True
