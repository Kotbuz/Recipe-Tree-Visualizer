from pathlib import Path

from app.recipes.providers.kubejs_custom_machinery_parser import _CM_START, _expand_function_calls
from app.recipes.providers.kubejs_script_parser import _read_call_arguments, _strip_js_comments

path = Path(r"P:\Practice\Recipe-Tree-Visualizer\LocalFiles\kubejs\server_scripts\custom_machinery\Recycling.js")
expanded = _expand_function_calls(_strip_js_comments(path.read_text(encoding="utf-8")))
for match in _CM_START.finditer(expanded):
    start = match.start()
    open_paren = expanded.find("(", start)
    args, args_end = _read_call_arguments(expanded, open_paren + 1)
    if len(args) < 2 or args[1].strip() != "100" or "fluid_recycler" not in args[0]:
        continue
    print(repr(expanded[args_end - 5 : args_end + 80]))
    break
