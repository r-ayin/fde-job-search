import io

p = r'<PROJECT_DIR>\vision\dom_tools.py'
s = io.open(p, encoding='utf-8').read()

start = s.index('JS_FIND_BY_TEXT = r"""')
end = s.index('"""', start + len('JS_FIND_BY_TEXT = r"""')) + 3

new_block = (
    'JS_FIND_BY_TEXT = r"""\n'
    '(() => {\n'
    '  const want = %s;\n'
    '  const scope = %s;\n'
    '  const root = scope ? document.querySelector(scope) : document;\n'
    '  if (!root) return null;\n'
    '  const els = [...root.querySelectorAll(\'a,button,div,span,li\')];\n'
    '  // 归一化空白后比较：BOSS 的按钮文本常带换行/多空格（如 "继续沟通\\n   "、\n'
    '  // "感兴趣 继续沟通"），用精确相等匹配会漏掉。\\s 在 JS 正则里含换行。\n'
    '  const norm = s => (s || \'\').replace(/\\s+/g, \' \').trim();\n'
    '  const w = norm(want);\n'
    '  const hit = els.filter(e => norm(e.innerText) === w);\n'
    '  if (!hit.length) return null;\n'
    '  // 页面常有隐藏的同名副本（响应式/移动端版本，尺寸为 0），\n'
    '  // 必须先按可见性过滤，否则会取到隐藏元素并误判为"找不到"（曾报 no_button）。\n'
    '  const visible = hit.filter(e => {\n'
    '    const r = e.getBoundingClientRect();\n'
    '    return r.width > 0 && r.height > 0;\n'
    '  });\n'
    '  if (!visible.length) return null;\n'
    '  // 在可见元素里取最深的（无其他可见匹配为其后代），避免命中外层容器\n'
    '  let target = visible[visible.length - 1];\n'
    '  for (const e of visible) {\n'
    '    const descendant = visible.some(o => o !== e && e.contains(o));\n'
    '    if (!descendant) { target = e; break; }\n'
    '  }\n'
    '  target.scrollIntoView({block: \'center\'});\n'
    '  const r = target.getBoundingClientRect();\n'
    '  if (r.width === 0 || r.height === 0) return null;\n'
    '  return JSON.stringify({\n'
    '    x: r.x + r.width / 2, y: r.y + r.height / 2,\n'
    '    w: r.width, h: r.height, text: norm(target.innerText),\n'
    '    cls: (target.className || \'\').toString().slice(0, 60)\n'
    '  });\n'
    '})()\n'
    '"""'
)

s = s[:start] + new_block + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print("已重写 JS_FIND_BY_TEXT")
