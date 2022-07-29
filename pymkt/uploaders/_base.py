from abc import ABC, abstractmethod


class Uploader(ABC):
    @abstractmethod
    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        ...
