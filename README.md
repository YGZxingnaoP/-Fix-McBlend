# mcblend (fork)

A fork of [mcblend](https://github.com/Nusiq/mcblend) **12.0.1** — a Blender
add-on that imports/exports Minecraft Bedrock Edition models and animations
(Blender 4.5).

The fork builds a usable armature out of an imported model. Upstream gives
every bone the same fixed shape:

```python
add_bone(edit_bones, 0.3, bone)      # every bone = an identical 0.3 stub
```

which makes the rig unusable for anything that depends on the bone axes
(bone-driven physics tools such as Bone Dynamics Pro, bone constraints, normal
posing) and also breaks the parenting of the cubes on the limbs.

## Changes

### 1. Logical skeleton — `mcblend/operator_func/imported_skeleton.py` (new module)

`compute_bone_shapes()` derives `head`/`tail` for every bone from the model
data:

| bone | `head` | `tail` |
|---|---|---|
| owns cubes | its pivot | pivot of the child that *continues* the bone — direction within 60° of the bone's own cube cloud and distance within `0.3×…2.5×` of that cloud's reach; if there is no such child, the far end of the bone's own cube cloud |
| no cubes | its pivot | unchanged from upstream: furthest child, or `leaf_length` away from the parent |

The bone locators keep the original transforms, so the importer stores the
original rest pose of every bone in the pose-bone property
`IMPORTED_REST_PROPERTY` (`store_imported_rest()`), and
`common.McblendObject.obj_matrix_world` reconstructs it via
`imported_obj_matrix()` / `imported_pose_matrix()`. Exported geometry and
animations are therefore identical to what unmodified bones would produce.

### 2. Cube parenting — `mcblend/operator_func/importer.py`

`ModelLoader.build_with_armature()` now places every cube explicitly instead of
relying on the bone-parenting math:

```python
cube_obj.matrix_world = bone_rest[bone.name] @ T(-bone_pivot) @ matrix_basis
```

`bone_rest` holds the world matrices of the bone locators, captured before they
are replaced by bones (the same values the rest property is built from). A cube
gets the transform of its own bone **and of all its ancestors**, rotated around
the pivot of its bone.

Fixes: cubes did not inherit the rotation of the parent bone — e.g. the forearm
kept the rest orientation of the upper arm instead of following it.

## Notes

- Only bone `tail` positions and bone connectivity (`use_connect`) change.
  Cube world matrices and the exported `json` are unchanged (verified by
  comparing two imports of the same model, one with upstream bone shapes).
- Because the bones get a new rest pose, animations that were keyed by hand
  against the old bone axes are affected when the model is re-imported into an
  existing `.blend`.

## Install

Copy `mcblend/` into Blender's add-on directory, e.g.

```
%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons\mcblend
```

then enable **Mcblend** in *Preferences → Add-ons*.
On Windows, `mcblend/apply_to_blender.bat` does the copy (quit and restart
Blender afterwards).

## License

MIT — Copyright (c) 2020 Artur D. (Nusiq), see `mcblend/LICENSE`.
This fork keeps the original copyright and license notice.
Upstream: <https://github.com/Nusiq/mcblend>
