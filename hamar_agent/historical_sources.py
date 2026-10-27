"""Owner-authorized historical access to the exact retained October dataset.

Not renewal, freshness, municipal permission or authorization to fetch content.
Only the byte-content-equivalent pinned approval/document records qualify.
Other sources and modified records retain normal expiry enforcement.
"""
from dataclasses import asdict
from datetime import date
import hashlib
import json

APPROVAL_PINS = {'hamar-sfo': '3fad55c96cb2f4a0ac87e19ba50b0b2f1ff1141a25f2a1f394faf2b7315f8e0e', 'hamar-byggesak': '10202fdc70706affa912970e9d6317cd521e53179611b3e57fe3610d4e5631cb', 'hamar-folkehelse': 'd1e15a16a524ef6b6f11e7c267f56218d332448bba2563eb3816990510cedd66', 'hamar-bibliotek': '2a014e05b804de33df33fdaad24a3a4d0d9a8711e9a7c4969f1e9f7738b4ee98', 'hamar-kommuneplan': '934dcf209715e553e53ec94d1d159de56c78bbafed9ac3f6b217e951444afa35', 'hamar-drikkevann': '0c841d7615aaae03550639891b6a8730ab8a436cc5b01fbb2d7ef82b87cfba3c', 'hamar-parkering': '2ac21ceecc1cf2ca5a40911c9afcb0483d097b2653b0694194deb033fb6a2694', 'hamar-luftkvalitet': 'ecca600fcdde77e8340b13d2f88209d466f7bb9e4a8361e0a403ce90cd9afd5e'}

DOCUMENT_PINS = {'hamar-sfo': '1cc6177c41bef63d076e6745218cc47850cd4e4e957ebabef7d09896a41f909a', 'hamar-byggesak': '08311fd202fe18736a6d130cc0a7673b0aaee3435ad21409d27390f8db97190d', 'hamar-folkehelse': '70bc3216e52c4ecea90c5cfddc3ee3d57bcd988064f47e3e28e2f0d53d787201', 'hamar-bibliotek': 'eb4c036f3e0159e7599764803c7a6537910ffd57825ccbfae385bd1b1a18446f', 'hamar-kommuneplan': '944618e7d6d2bc2f5da2dd99fca2e4c2abaee09d039da7154c8e605720e452f7', 'hamar-drikkevann': '64cbdc1f7366f8524a01fac426748e84d455879c83ef37c5fb04f732883b5033', 'hamar-parkering': 'a727e60ad2e96e09942b0603dc32bb7bc8a8f04b72373c07c5c4b342a7ecee13', 'hamar-luftkvalitet': 'b57a356ba9c1fcfa6d76d5c43126641eb8799b1ddfeb95f666a8339f96cdcf6a'}

HISTORICAL_WARNING = "Historisk kildemateriale: godkjenningen er utløpt. Ikke nygodkjent eller oppdatert. Kontroller gjeldende opplysninger hos kommunen."


def _digest(record):
    return hashlib.sha256(json.dumps(asdict(record), ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def retained_approval(approval, *, today=None):
    return (date.fromisoformat(approval.reviewed_on) <= (today or date.today())
            and APPROVAL_PINS.get(approval.source_id) == _digest(approval))


def retained_document(document):
    return DOCUMENT_PINS.get(document.source.id) == _digest(document)
