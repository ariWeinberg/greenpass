import base64
import fitz
import json

from io import BytesIO
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.exceptions import InvalidSignature
from PIL import Image
from pyzbar import pyzbar

from .base import Verifier


class GreenPassVerifier(object):
    def __init__(self, data_bytes):
        self.validate_bytes(data_bytes)

        sig, self.payload = data_bytes.split(b"#", maxsplit=1)
        self.signature = base64.decodebytes(sig)
        self.data = json.loads(self.payload)

        self.validate_data()
        self.details = self.get_details()
        self.digest = self.get_digest()

        self.ec_cert = self.get_cert_path("IL-NB-DSC-01.pem")
        self.rsa_cert = self.get_cert_path("RamzorQRPubKey.pem")

    def validate_data(self):
        ct = self.data["ct"]
        if ct not in (1, 2):
            raise Exception(f"Unknown certificate type {ct=}")

    def get_details(self):
        details = []
        data = self.data
        if data["ct"] == 1:
            for i in range(len(data["p"])):
                details.append(
                    {
                        "id_num": data["p"][i]["idl"],
                        "valid_by": data["p"][i]["e"],
                        "cert_id": data["id"],
                    }
                )
        elif data["ct"] == 2:
            details.append(
                {
                    "id_num": data["idl"],
                    "valid_by": data["e"],
                    "cert_id": data["id"],
                }
            )
        return details

    def get_digest(self):
        ct = self.data["ct"]
        if ct == 1:
            digest = self.payload.decode().encode("utf8")
        elif ct == 2:
            h = hashes.Hash(hashes.SHA256())
            h.update(self.payload)
            digest = h.finalize()
        return digest

    def verify(self):
        for d in self.details:
            print(f"\tIsraeli ID Number {d['id_num']}")
            print(f"\tID valid by {d['valid_by']}")
            print(f"\tCert Unique ID {d['cert_id']}")

        certs = [
            [
                self.rsa_cert,
                [
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                ],
            ],
            [self.ec_cert, [ec.ECDSA(hashes.SHA256())]],
        ]
        for cert, method in certs:
            with open(cert, "rb") as f:
                k = serialization.load_pem_public_key(f.read())
                try:
                    k.verify(self.signature, self.digest, *method)
                    return True
                except InvalidSignature:
                    pass
        else:
            return False


class EuroVerifier(Verifier):
    def verify(self):
        return False
