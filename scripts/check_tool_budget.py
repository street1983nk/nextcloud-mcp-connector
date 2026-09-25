"""CI gate for the size of the ``tools/list`` response.

Bytes instead of tokens on purpose: deterministic, no model choice, no extra package.
Exit code 1 when the budget is exceeded, plus the five biggest tools so a regression is
immediately attributable.
"""

import asyncio
import json
import sys

from mcp import Client

from mcp_connector.server import mcp

# Armed value, not a decorative one. A budget far above the measurement never fails and
# therefore never protects anything, which was the state until the end of phase 1.
#
#   Measurement 2026-08-14, all 15 curated tools registered: 10643 bytes
#   Budget      10643 + 15 percent = 12239, rounded up to the next 500 = 12500 bytes
#
#   Measurement 2026-08-21, all 18 curated tools registered: 12801 bytes
#   Budget      12801 + 15 percent = 14721, rounded up to the next 500 = 15000 bytes
#
#   Measurement 2026-08-21, all 20 curated tools registered: 14312 bytes
#   Budget      unchanged at 15000, because the measurement fits below it
#
#   Measurement 2026-08-21, same 20 tools, cursor description of tables_browse and
#               talk_browse says which level hands one out (review finding IN-04): 14358 bytes
#   Budget      unchanged at 15000, because the measurement fits below it
#
#   Measurement 2026-08-24, all 21 curated tools registered (mail_browse of phase 10): 15736
#               bytes
#   Budget      15736 + 15 percent = 18096, rounded up to the next 500 = 18500 bytes
#               An intermediate raise, marked as such when it was made; the line below is
#               the one that replaced it.
#
#   Measurement 2026-08-24, same 21 tools, schema diet of the five tools of milestone v1.2
#               plus the more honest description of prepare_context: 15612 bytes
#   Budget      15612 + 15 percent = 17953, rounded up to the next 500 = 18000 bytes
#   Anchored    on a measurement of phase 11, so this number is no longer an intermediate
#               one and there is no pending task left to point at. The way it got there is
#               the whole point: the diet of the five tools took 157 bytes off the surface
#               (mail_browse 1377 -> 1331, talk_browse 886 -> 858, tables_create_row
#               780 -> 746, tables_browse 772 -> 751, talk_send 648 -> 620), and 33 of the
#               15769 it started from had just been spent on naming Talk and Mail in the
#               description of prepare_context. Anchoring on the old 15736 would have
#               written 18500 a second time and called it work.
#
#               17500 was the other number TOOL-15 would have accepted, and it was not
#               reached: it needs 15217 bytes, so 395 more than the diet found. The five
#               tools carry 1729 bytes of prose inside 4306 bytes of tool, the rest being
#               names, types, enums, defaults and the ``title`` keys pydantic generates. 395
#               bytes is 23 percent of every word those five tools say, and the words left
#               are the filter grammar, the two "a timeout does not mean nothing was
#               written" warnings and the sentence that says mail is read only. Each of
#               those is information a model has nowhere else, so the cut stopped here and
#               the gate says 18000 instead of a number bought with an omission. The
#               untaken cut worth naming is the ``title`` key of every schema property
#               (~140 bytes in mail_browse alone, over a kilobyte across the surface): it
#               is pure derivation of the parameter name, but removing it changes how every
#               one of the 21 schemas is generated, which is a decision of its own and not
#               a diet of five descriptions.
#
#   Measurement 2026-09-20, all 22 curated tools with chunked files_download: 16412 bytes
#   Budget      unchanged at 18000, because the measured surface still fits below the
#               existing ceiling. The tool has three arguments; its description names the
#               continuation contract that supports files of any total size in 8 MiB chunks.
#
# The older lines stay where they are: a regression is only attributable when the number it
# regressed from is still readable. The first 2026-08-21 line is the tables_browse and
# tables_create_row pair of phase 8 (751 and 780 bytes), which took the surface past the
# gate of phase 1 exactly as it was meant to. The second is the talk_browse and talk_send
# pair of phase 9 (861 and 648 bytes), and it raises nothing: a budget is lifted against a
# measurement that needs it, never out of habit. The third is 46 bytes of wording, spent
# because both tools now refuse a cursor on a level that has none and the schema is where a
# model reads which level that is; it left 642 bytes of headroom. The fourth is the single
# ``mail_browse`` of phase 10 at 1377 bytes, which is exactly the twenty-first tool the
# paragraph below was written for: it tripped the gate at 15000, and the gate did its job.
# The fifth is the first line of this file that lowers the number instead of raising it, and
# it is the only kind of line that needs no justification beyond its own measurement.
#
# At ~4 bytes per token the whole surface costs roughly 4k tokens in every single session of
# every client. The twenty-second tool was added with an explicit measurement and without
# raising the ceiling. A future tool or a description that grows into a paragraph still has
# to fit this gate or justify a new measurement and budget here, so a regression stays
# attributable.
BUDGET_BYTES = 18_000

# The second claim, and the one that actually reports a regression. A total with headroom
# says nothing about a single tool: today's outlier ``calendar_create_event`` sits at 1351
# bytes, so one new tool with a paragraph of prose fits under the total while being twice
# the size of everything around it. That is the change worth catching, and only a per tool
# ceiling catches it.
#
# The unit is the same as the one of the total, and it says bytes because it measures bytes
# (review finding IN-03). Until 2026-08-21 this one number was measured on characters while
# the total was measured on the UTF-8 encoding, so a tool with non-ASCII text in its
# description was undercounted against its own ceiling. Both are bytes now.
#
#   Measurement 2026-08-21, per tool on bytes for the first time: unchanged, biggest tool
#   ``calendar_create_event`` at 1351 bytes. Every description of this surface is ASCII, so
#   the two units happen to agree today; the point of the change is that they keep agreeing
#   when one of them is not ASCII any more.
#
#   Measurement 2026-08-24, biggest tool is ``mail_browse`` at 1377 bytes: unchanged, and
#   deliberately so. This ceiling is the real guard, so a tool that reaches it gets a shorter
#   description and never a higher limit (A5 of the phase 10 research). ``mail_browse`` was
#   1585 bytes when it was first written and it was cut, not exempted.
#
#   Measurement 2026-08-24 after the diet of plan 11-07: unchanged at 1400 on purpose, and
#   the reason is arithmetic rather than habit. ``mail_browse`` fell to 1331 and is not the
#   outlier any more; the biggest tool is ``calendar_create_event`` at 1351, a tool of phase 1
#   that this milestone never touched. The rule this file uses for the total (measurement plus
#   15 percent) would give 1553 here and therefore a raise, which the paragraph above forbids,
#   so it does not apply to a ceiling that is already tighter than it: 1400 leaves 49 bytes
#   over the biggest tool, 3.6 percent, against the 15 percent the total gets. The only
#   lowering with any room in it would land just over 1351 and would freeze the wording of
#   ``calendar_create_event`` in a phase that is not about it: the next honest sentence there
#   would trip a per tool alarm while the total still has 2388 bytes free, which is a gate
#   firing for the wrong reason. So the number stays, and it stays armed.
MAX_TOOL_BYTES = 1400


async def main() -> int:
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.list_tools()

    payload = result.model_dump(by_alias=True, exclude_none=True, mode="json")
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    size = len(blob.encode("utf-8"))
    per_tool = sorted(
        (
            (
                # ``.encode("utf-8")`` and not ``len`` of the string: the same unit as the
                # total above, so the two limits of this gate measure the same thing (IN-03).
                len(json.dumps(tool, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
                tool["name"],
            )
            for tool in payload["tools"]
        ),
        reverse=True,
    )

    print(f"tools/list: {size} bytes, {len(payload['tools'])} tools, budget {BUDGET_BYTES}")
    for tool_size, name in per_tool[:5]:
        print(f"  {name}: {tool_size} bytes")

    if size > BUDGET_BYTES:
        print("FAIL: tools/list exceeds the token budget", file=sys.stderr)
        return 1

    too_big = [(name, tool_size) for tool_size, name in per_tool if tool_size > MAX_TOOL_BYTES]
    if too_big:
        for name, tool_size in too_big:
            print(
                f"FAIL: {name} is {tool_size} bytes, above the per tool ceiling "
                f"of {MAX_TOOL_BYTES}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
