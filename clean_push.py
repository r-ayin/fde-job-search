import io

# 1) 本地删除
p = r'E:\fde-job-search\resume_supp_results.json'
import os
if os.path.exists(p):
    os.remove(p)
    print("已删除 resume_supp_results.json")

# 2) 导出脚本加入排除规则（防止下次再带进来）
ep = r'<PROJECT_DIR>\export_anonymized.py'
s = io.open(ep, encoding='utf-8').read()
old = '    "audit_tsv.txt",\n'
new = '    "audit_tsv.txt",\n    "resume_supp_results.json",   # \u6295\u9012\u884c\u4e3a\u8bb0\u5f55\n'
if 'resume_supp_results.json' not in s:
    assert old in s, "anchor"
    s = s.replace(old, new, 1)
    io.open(ep, 'w', encoding='utf-8').write(s)
    print("已在导出脚本加入排除规则")
else:
    print("导出脚本已含该规则")
