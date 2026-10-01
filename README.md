# Mcblend (modified fork)

A modified fork of **[Mcblend](https://github.com/Nusiq/mcblend)** — a Blender
addon for importing/exporting Minecraft **Bedrock Edition** models and
animations. Based on Mcblend **12.0.1** (MIT, by Nusiq).

本仓库是 mcblend 12.0.1 的**修改版**，主要用于：让导入后的骨架更贴合模型结构
（便于绑定物理插件、例如骨骼力学 / Bone Dynamics Pro），并保证**导出的模型几何
与源文件仍然一致**。

---

## 相对官方 mcblend 12.0.1 改了什么

### ① 逻辑骨架（Logical skeleton）

官方 12.0.1 给每根骨骼都是**同一个固定长度的短柱**（`add_bone(edit_bones, 0.3, bone)`），
所有骨骼朝向相同，物理插件没法用。

现在改为按模型数据计算每根骨骼的 `head` / `tail`（新增模块
`mcblend/operator_func/imported_skeleton.py`）：

- `head` = 该骨骼的 pivot（含父级旋转影响，与 Blockbench 显示的关节位置一致）
- `tail` = 下面的规则算出来
- 因为骨骼被"重塑"过，导入时把**原始的 rest 变换**存进骨骼自定义属性
  `IMPORTED_REST_PROPERTY`；导出时由它重建骨骼变换
  （`common.py` 的 `obj_matrix_world` → `imported_obj_matrix`），
  **所以导出的模型/动画依旧与源文件一致**。

### ② 方块（cubes）的世界矩阵修复

骨骼重塑后，方块不能靠 Blender 的自动父子继承位置。现在在
`importer.py::ModelLoader.build_with_armature` 里显式设置：

```python
cube_obj.matrix_world = bone_rest[bone.name] @ T(-pivot) @ matrix_basis
```

即方块带上**自己骨骼 + 所有父骨骼**的变换、并绕骨骼 pivot 旋转。

**修掉的现象**：上臂正常、小臂"断掉/丢角度"（小臂方块没有继承上臂旋转）。

### ③ 骨骼 tail 规则细化

不再一律取"最远的直接子骨骼"，而是：

| 骨骼类型 | tail 取法 |
|---|---|
| **有自己的方块** | 取**延续自己**的那个子骨骼 pivot：方向在自己方块云 60° 以内、距离在自身方块尺度 0.3×–2.5× 之间；没有合格的子骨骼时，取自己方块云里离 head 最远的点（长度 = 自身部件尺寸） |
| **没有方块**（纯关节） | 保持官方规则：最远的直接子骨骼；没有子骨骼则朝远离父级方向伸 `leaf_length` |

**修掉的现象**：
- `Front_hairline` 的 tail 只有 1.1 cm（物理体退化）→ 0.338 m
- `LeftForeArm`/`RightForeArm` 的 tail 1.588 m（比自身部件长 6.4 倍，物理上变成巨型摆）→ 0.344 m
- 叶子骨骼不再一律 0.3 m，改为按自身方块尺寸

### ④ 其它

- `mcblend/apply_to_blender.bat`：本机部署脚本（把插件 xcopy 到 Blender 插件目录），
  已在 `.gitignore` 中忽略

---

## 验证结论（本次改动）

- 方块世界矩阵：101 个方块逐一比对，差异 **0 个**（最大 6.2e-06 m，浮点噪声）
- 骨骼 head：**0 / 141** 移动
- `use_connect`：78 → 77（掉 3 / 增 2）
- 导出 JSON：最大差异 1e-03（= 导出自身取整步长），超取整的字段 **0 处**

## 安装

1. 把 `mcblend/` 放到 Blender 的插件目录，例如
   `%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons\mcblend`
2. Blender → 编辑 → 偏好设置 → 插件 → 启用 **Mcblend**
3. （可选）Windows 下直接运行 `mcblend/apply_to_blender.bat` 完成拷贝，然后**完全退出并重启 Blender**

## 许可

MIT License — 版权归原作者 **Artur D. (Nusiq)**，见 `mcblend/LICENSE`。
本仓库为其修改版，保留原始版权与许可声明。

- 上游项目：https://github.com/Nusiq/mcblend
- 文档：https://mcblend.readthedocs.io
