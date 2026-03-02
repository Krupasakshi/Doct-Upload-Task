from abc import ABC, abstractmethod
import os

UPLOAD_DIR = "uploads"

class StorageService(ABC):

    @abstractmethod
    def upload(self, file, filename: str) -> str:
        pass

    @abstractmethod
    def delete(self, filename: str):
        pass

    @abstractmethod
    def get_url(self, filename: str) -> str:
        pass


class LocalStorageService(StorageService):

    def upload(self, file, filename: str) -> str:
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(file.file.read())

        return filename

    def delete(self, filename: str):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    def get_url(self, filename: str) -> str:
        return f"/uploads/{filename}"