from ._avistaznetwork import AvistaZNetworkUploader


class AvistaZUploader(AvistaZNetworkUploader):
    name = "AvistaZ"
    abbrev = "AvZ"

    year_in_series_name: bool = True
    keep_dubbed_dual_tags: bool = True
