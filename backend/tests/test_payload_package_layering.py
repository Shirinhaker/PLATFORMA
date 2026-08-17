"""`business_online/payload` paketida aylanma import bo'lmasin.

2 159 qatorlik `payload_service.py` mavzu bo'yicha bo'linganda eng katta
xavf — modullarning bir-birini chaqirib, halqa hosil qilishi. Halqa
paydo bo'lsa Python ba'zan ishlaydi, ba'zan `ImportError` beradi —
import tartibiga qarab. Bunday xato jonli serverda chiqadi va sababi
uzoq izlanadi.

Bu test bog'liqlik grafini o'qiydi va halqani darrov ko'rsatadi.

Bo'lish paytida ikkita halqa haqiqatan topildi:
`helpers` -> `spec` -> `helpers`. Ikkalasi ham funksiyani to'g'ri
modulga ko'chirish bilan yechildi.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "app" / "business_online" / "payload"
PREFIX = "app.business_online.payload."


def _graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        edges = {
            (node.module or "").removeprefix(PREFIX)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith(PREFIX)
        }
        graph[path.stem] = edges
    return graph


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    state: dict[str, int] = {}

    def walk(node: str, path: list[str]) -> None:
        state[node] = 1
        for neighbour in sorted(graph.get(node, ())):
            if state.get(neighbour) == 1:
                found.append([*path[path.index(neighbour) :], neighbour])
            elif state.get(neighbour, 0) == 0:
                walk(neighbour, [*path, neighbour])
        state[node] = 2

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            walk(node, [node])
    return found


def test_payload_package_has_no_import_cycles():
    cycles = _cycles(_graph())
    assert cycles == [], "Aylanma import topildi: " + "; ".join(
        " -> ".join(cycle) for cycle in cycles
    )


def test_constants_module_depends_on_nothing():
    """Konstantalar — eng past qatlam. Ular hech kimni chaqirmasligi kerak."""

    assert _graph()["constants"] == set()


def test_every_module_stays_readable():
    """Paketdagi hech bir modul 500 qatordan oshmasin.

    Bo'lishning butun maqsadi shu edi. Umumiy `check_file_length.py`
    ham buni ushlaydi, lekin bu yerda sabab yaqinroq turadi.
    """

    oversized = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in PACKAGE.glob("*.py")
        if len(path.read_text(encoding="utf-8").splitlines()) > 500
    }
    assert oversized == {}


def test_shim_is_gone_and_package_is_the_only_entry_point():
    """Eski `payload_service.py` qobig'i o'chirilgan.

    U bo'lish paytida chaqiruv joylarini buzmaslik uchun qoldirilgandi.
    Vaqtinchalik yechim o'z vazifasini bajardi va endi zarar keltiradi:
    turgan ekan, yangi dasturchi eski yo'ldan yurib, mavzuli paketni
    umuman ko'rmasligi mumkin. Bosqich 3.2 da o'chirildi.
    """

    assert not (PACKAGE.parent / "payload_service.py").exists()

    from app.business_online.payload import BusinessOnlinePayloadService
    from app.business_online.payload.actions import apply_action, refresh_derived
    from app.business_online.payload.service import locked_profile

    assert BusinessOnlinePayloadService is not None
    assert callable(apply_action)
    assert callable(refresh_derived)
    assert callable(locked_profile)


def test_no_wildcard_imports_inside_the_package():
    """`import *` nima eksport qilinishini o'qib bilishga imkon bermaydi.

    Qobiqlarda aynan shu ishlatilardi va u maxfiy nomlarni jimgina
    tushirib qoldirardi.
    """

    offenders = [
        path.name
        for path in sorted(PACKAGE.glob("*.py"))
        if "import *" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
