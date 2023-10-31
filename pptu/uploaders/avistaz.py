from ._avistaznetwork import AvistaZNetworkUploader


class AvistaZUploader(AvistaZNetworkUploader):
    name: str = "AvistaZ"
    abbrev: str = "AvZ"

    year_in_series_name: bool = True
    keep_dubbed_dual_tags: bool = True
