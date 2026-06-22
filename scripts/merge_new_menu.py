"""Merge data/new_menu_items.json into data/vk_menu.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "data" / "vk_menu.json"
NEW = ROOT / "data" / "new_menu_items.json"

UPDATES = {
    "Сыр \"Домашний\"": {
        "image_url": "https://i.wfolio.ru/x/Sjpgrm2v20FR6Cth5viRk6Iir5aoqG4h/ZXWGJmu7EQlhnv6D9ELHSMzGOBuFicXp/OGcM34slpvmXTMkbuJagSV1xA4akZdWt/iGTrK_jx2PJdzPpMyVlbGIyR5mAu9UqG/rL-5DUxboiaoOuXyk54XGX-OT-NQ5DIt/t4cadjULppTx1gEZEyG7Eqk7p-JphqNA/E-VjBOssplpcT44Fqigxab1SM3EHSrfa/U4UZrdXN1szhc66D2tDiZuIGXN9MT8VC/iDb7e4k84EwljCj8kHh1ijnQCSofS0Ee/z1EPDqn-_EA5BSdvUSskgmaxv9viWtsz/mRadIQvWUEOjvij8FLdV7nRCBAJ5qi8A/1Qcr6XbYkgXvDdKYadOPzLyh8LV041jv/KfEHfsKyUL8mNDaHtETBYawM-AGC5Tqs/Vy93uwhTGOb90orPwQ-ZTt6x3hDKeF2K/LESRS0LcjPbpGR-Oi0hsBnek3fsL3z7M/ananACFxSjiMvVxgkeIv41hmG8CGc3zd/x_C2NTysz2DBt2lDJYvPK0momSTA3p69/mA9Ktv0W6uo.jpg",
    },
    "Ассорти шашлыков": {
        "image_url": "https://i.wfolio.ru/x/Erhj60RfGoSDn6LYN1vjjheZsgmFENWg/70nl7vp0vtA5I_3875z-74SYoU4uutGd/xstRKgtuKfAuaesT0g7GCj5r5jVhYYJO/czeCPV64a88WPNVdvAGyHihjk55jsR3q/fDWeOlbRKvFPIbN5Tc6YUsyZS-b90JuD/zBNyHXOjg-RczmtPGhlGv_kfwrfhlgdq/9vsmwW-CzmBcQntlWtliWJPDAmp0njfH/q1aYzK14kThA6UvxmrIfivT-KVEQG10G/l4RBzQ_eK9tUE-wk--3AB7VmdyRkGoPN/8ScFDhTMZJT6s1pJ31od3DefoCZGMfY0/_fPn1b_P3AF7MinQ5VihaSdl81oShu_m/EJ_0936smYDEaR78TNo_84C-xJ3U4Kr_/yOpxiPnsAjllGOOuLyeXFiiaKdMwtvCi/TrZ-JjfsCWGw-e3Jr94aSmx2QYgAq0qv/wNlBN7FnDaQekTVSRlGwfn8VH3m4X1iq/aTO5BHRZ5o1hVkUQEPvarwu3ZigRwBxf/dyM4euXEC7YrvDh6XQ_N7qJLlHgBGFkj/egYPy-qLCOE.jpg",
    },
    "Печень по-королевски": {
        "image_url": "https://i.wfolio.ru/x/Sjpgrm2v20FR6Cth5viRk6Iir5aoqG4h/ZXWGJmu7EQlhnv6D9ELHSMzGOBuFicXp/OGcM34slpvmXTMkbuJagSV1xA4akZdWt/iGTrK_jx2PJdzPpMyVlbGIyR5mAu9UqG/rL-5DUxboiaoOuXyk54XGX-OT-NQ5DIt/t4cadjULppTx1gEZEyG7Eqk7p-JphqNA/E-VjBOssplpcT44Fqigxab1SM3EHSrfa/U4UZrdXN1szhc66D2tDiZuIGXN9MT8VC/iDb7e4k84EwljCj8kHh1isTHLiGFzibX/dza-Md6qUWwebZz-pSy7OqoLwJuL_bUo/e7HuB-JK3O9_i6NaMOd5WiusNTCmzEZF/Bt4SB8_lUHOsLHrSy6jMeb-xM3Mo0YTq/OMypl2jUK0HhWPDQHnTPXYKVf6-VPIN7/Nc-fCZzSHu8hQa2wBpbi6kFjS7MsOR9g/fzwf5d_G3b8wHJnLDAIwbwR0NJLQVP_f/vORZeaVi77RMCsppYpVcTaQ1edHlCEZq/PGORV-oYMrq-23tXj1x7EA1oid_6HTg7/LgcYTaNcjHU.jpg",
    },
}

REMOVE_NAMES = {"Лаваш", "Куриное филе"}


def norm(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def main() -> None:
    menu = json.loads(MENU.read_text(encoding="utf-8"))
    new_items = json.loads(NEW.read_text(encoding="utf-8"))
    by_norm = {norm(item["name"]): item for item in menu}

    menu = [item for item in menu if item["name"] not in REMOVE_NAMES]

    added = 0
    for raw in new_items:
        key = norm(raw["name"])
        if key in by_norm:
            by_norm[key].update(raw)
            continue
        menu.append(raw)
        by_norm[key] = raw
        added += 1

    for item in menu:
        patch = UPDATES.get(item["name"])
        if patch:
            item.update(patch)

    MENU.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged: +{added} new, total {len(menu)}, removed {len(REMOVE_NAMES)} duplicates")


if __name__ == "__main__":
    main()
