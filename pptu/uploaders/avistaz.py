from ._avistaznetwork import AvistaZNetworkUploader


class AvistaZUploader(AvistaZNetworkUploader):
    name = "AvistaZ"
    abbrev = "AvZ"

    year_in_series_name = True
    keep_dubbed_dual_tags = True
