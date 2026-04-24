# 测试说明

当前后端测试使用 Python 标准库 `unittest`，推荐在 `mini-claw` 环境下运行。

## 完整回归

```powershell
D:/develop/miniconda3/envs/mini-claw/python.exe -m unittest discover -s tests -p "test_*.py"
```

当前完整回归覆盖：

- API smoke
- session history 与 session summary
- structured memory record 写入与检索
- memory dreaming 与高置信自动晋升
- skill retrieval / selection
- draft extraction
- governance judge
- merge preview / versioning / rollback

## 单文件运行

```powershell
D:/develop/miniconda3/envs/mini-claw/python.exe -m unittest discover -s tests -p "test_retrieval_quality.py"
```

也可以直接指定模块：

```powershell
D:/develop/miniconda3/envs/mini-claw/python.exe -m unittest tests.test_phase_d_merge_versioning
```

如果直接指定模块时遇到 `test_utils` 导入问题，优先使用 `discover -s tests` 的形式。
