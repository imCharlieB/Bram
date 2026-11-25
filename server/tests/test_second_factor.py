import base64
import json

import pytest
from test_web import PASSWORD, page  # noqa: F401

from bram import second_factor, web
from bram.second_factor import PERIOD, check, code_at, matching_step

RFC = base64.b32encode(b"12345678901234567890").decode()


# RFC 6238, appendix B, last six digits.
@pytest.mark.parametrize(("at", "code"), [
    (59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (20000000000, "353130")])
def test_matches_the_standard(at, code):
    assert code_at(RFC, at // PERIOD) == code


def test_a_code_works_once_and_only_near_its_time():
    record = {"secret": RFC, "last": 0, "recovery": []}
    now = 1_700_000_000
    code = code_at(RFC, now // PERIOD)
    used = check(record, code, now)
    assert used and check(used, code, now) is None
    assert check(record, code, now + PERIOD) and check(record, code, now + 3 * PERIOD) is None
    for bad in (None, 5, "", "abcdef", code + "0", "١" * 6, [code]):
        assert matching_step(RFC, bad, now, 0) is None and check(record, bad, now) is None


class Phone:
    def __init__(self, monkeypatch):
        self.now = 1_700_000_000.0
        monkeypatch.setattr(web, "wall", lambda: self.now)

    def code(self):
        self.now += PERIOD
        return code_at(self.secret, int(self.now // PERIOD))


@pytest.fixture
async def phone(page, monkeypatch):  # noqa: F811
    p = Phone(monkeypatch)
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    assert (await page.post("factor-start", {"confirm": "wrong"})).status == 403
    p.secret = (await (await page.post("factor-start", {"confirm": PASSWORD})).json())["secret"]
    return p


async def turn_on(page, phone):  # noqa: F811
    response = await page.post("factor-on", {"code": phone.code()})
    assert response.status == 200
    return (await response.json())["recovery"]


async def sign_in(page, **extra):  # noqa: F811
    page.http.cookie_jar.clear()
    return await page.post("login", {"user": "owner", "password": PASSWORD, **extra})


async def test_turning_on_needs_a_right_code(page, phone):  # noqa: F811
    assert (await page.get("/api/factor-qr")).status == 200
    assert (await page.post("factor-on", {"code": "000000"})).status == 400
    assert page.settings.factor() is None
    recovery = await turn_on(page, phone)
    assert len(recovery) == 8 and page.settings.factor() is not None
    stored = json.dumps(page.settings.factor())
    assert not any(code in stored for code in recovery)
    assert (await page.get("/api/factor-qr")).status == 404  # never shown again
    assert (await page.post("factor-start", {"confirm": PASSWORD})).status == 400


async def test_password_alone_does_not_sign_in(page, phone):  # noqa: F811
    await turn_on(page, phone)
    response = await sign_in(page)
    assert await response.json() == {"need_code": True}
    assert (await page.get("/api/status")).status == 401
    assert (await sign_in(page, code="000000")).status == 403
    code = phone.code()
    assert (await sign_in(page, code=code)).status == 200
    assert (await page.get("/api/status")).status == 200
    assert (await sign_in(page, code=code)).status == 403  # replay


async def test_a_wrong_password_never_reveals_the_factor(page, phone):  # noqa: F811
    await turn_on(page, phone)
    page.http.cookie_jar.clear()
    response = await page.login("wrong password 12")
    assert response.status == 403 and "need_code" not in await response.json()


async def test_code_guesses_lock_out_even_between_right_passwords(page, phone):  # noqa: F811
    await turn_on(page, phone)
    for _ in range(5):
        assert (await sign_in(page, code="000000")).status == 403
        assert (await sign_in(page)).status in (200, 429)
    assert (await sign_in(page, code=phone.code())).status == 429


async def test_recovery_code_works_once(page, phone):  # noqa: F811
    recovery = await turn_on(page, phone)
    assert (await sign_in(page, code=recovery[0].upper())).status == 200
    assert (await sign_in(page, code=recovery[0])).status == 403


async def test_turning_off_needs_both(page, phone):  # noqa: F811
    await turn_on(page, phone)
    assert (await page.post("factor-off", {"confirm": PASSWORD})).status == 400
    assert (await page.post("factor-off", {"confirm": "x", "code": phone.code()})).status == 403
    assert page.settings.factor() is not None
    assert (await page.post("factor-off", {
        "confirm": PASSWORD, "code": phone.code()})).status == 200
    assert page.settings.factor() is None


async def test_wrong_codes_lock_turning_off(page, phone):  # noqa: F811
    await turn_on(page, phone)
    answers = [(await page.post("factor-off", {
        "confirm": PASSWORD, "code": "000000"})).status for _ in range(6)]
    assert answers[-1] == 429


async def test_changing_the_password_keeps_it_and_reset_removes_it(page, phone):  # noqa: F811
    await turn_on(page, phone)
    await page.post("password", {"new": "another good password", "confirm": PASSWORD})
    assert page.settings.factor() is not None
    page.settings.reset_login()
    assert page.settings.factor() is None


async def test_the_secret_is_never_in_the_log_or_profile(page, phone):  # noqa: F811
    recovery = await turn_on(page, phone)
    rows = " ".join(str(dict(r)) for r in page.audit.recent(50))
    profile = await (await page.get("/api/profile")).text()
    for text in (phone.secret, recovery[0]):
        assert text not in rows and text not in profile
    assert json.loads(profile)["factor"] is True


async def test_an_abandoned_setup_expires(page, phone):  # noqa: F811
    page.now += 700
    assert (await page.post("factor-on", {"code": phone.code()})).status == 400
    assert (await page.get("/api/factor-qr")).status == 404
    assert second_factor.RECOVERY == 8
