'''
Utilities related to the original transformations of the imported models.

.. important::

    The importer re-shapes the imported bones into a logical skeleton (see
    :func:`compute_bone_shapes`). This changes the rest transformation of
    every bone.

    Mcblend uses the transformation of the bones to store the transformation
    of the Minecraft bones - the exporter reads the transformation of every
    bone with :attr:`McblendObject.obj_matrix_world`. Because of that the
    transformations read from an armature with re-shaped bones no longer
    describe the model that was imported.

To solve that problem the importer remembers the original rest transformation
of every bone in the custom property :data:`IMPORTED_REST_PROPERTY`. The
functions in this module use it to reconstruct the transformation that the
bone would have if its rest transformation was not changed.

The reconstructed transformation is defined as::

    V(t) = W(t) @ K
    K    = W(0)^-1 @ V(0)          # constant, different for every bone
    W(t) = the transformation that the bone actually has in Blender
    V(0) = original rest transformation of the bone (from the property)

Thanks to that definition ``V(t) @ V(0)^-1`` is always equal to
``W(t) @ W(0)^-1``. That expression is the rigid motion of the bone relative
to its rest pose, in other words the motion of the vertices (cubes, polymesh,
locators) attached to the bone. Reconstructing ``V`` therefore guarantees that
the exported models and the exported animations deform the model in the exact
same way as Blender does.
'''
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import math

from mathutils import Euler, Matrix, Vector

from .exception import ImporterException

if TYPE_CHECKING:
    from bpy.types import PoseBone
    from .common import McblendObject
    from .importer import ImportBone
    from .extra_types import Vector3d


IMPORTED_REST_PROPERTY = 'mcblend_imported_rest'
'''
The name of the custom property stored on the pose bones of the armatures
created by the importer. It holds the original rest transformation of the
bone (a flat list of the 16 values of a 4x4 matrix, in the armature space).

The property is used by :func:`imported_pose_matrix` and (indirectly) by
:attr:`McblendObject.obj_matrix_world`. Deleting it makes the given bone
behave like a bone that was not created by the importer.
'''


# ---------------------------------------------------------------------------
# Storing/reading the original rest transformation
# ---------------------------------------------------------------------------
def _matrix_to_list(matrix: Matrix) -> List[float]:
    '''Converts a 4x4 matrix into a flat list of 16 floats.'''
    return [value for row in matrix for value in row]


def _list_to_matrix(values: Any) -> Optional[Matrix]:
    '''
    Converts a flat list of 16 floats into a 4x4 matrix. Returns ``None``
    when the list doesn't contain exactly 16 values.
    '''
    result = list(values)
    if len(result) != 16:
        return None
    return Matrix((
        result[0:4], result[4:8], result[8:12], result[12:16]))


def store_imported_rest(pose_bone: 'PoseBone', matrix: Matrix) -> None:
    '''
    Remembers the original rest transformation of an imported bone.

    :param pose_bone: the pose bone that should store the transformation.
    :param matrix: the original rest transformation of the bone (in the
        armature space) - this is the transformation that the bone would have
        if the importer didn't change its shape.
    '''
    pose_bone[IMPORTED_REST_PROPERTY] = _matrix_to_list(matrix)


def get_imported_rest(pose_bone: 'PoseBone') -> Optional[Matrix]:
    '''
    Reads the original rest transformation of an imported bone.

    :param pose_bone: the pose bone to read the transformation from.
    :returns: the original rest transformation of the bone or ``None`` when
        the bone wasn't created by the importer.
    '''
    stored = pose_bone.get(IMPORTED_REST_PROPERTY)
    if stored is None:
        return None
    return _list_to_matrix(stored)


# ---------------------------------------------------------------------------
# Reconstructing the transformations of the imported bones
# ---------------------------------------------------------------------------
def imported_pose_matrix(pose_bone: 'PoseBone') -> Optional[Matrix]:
    '''
    Returns the transformation (in the armature space) that the bone would
    have right now if the importer didn't change its rest transformation.

    The returned matrix (``V``) is defined as ``pose_bone.matrix @ K`` where
    ``K = rest(original)^-1 @ rest(actual)``. Thanks to that the rigid motion
    of the bone relative to its rest pose is the same as the rigid motion of
    the actual bone, so everything attached to the bone (cubes, polymorphic
    meshes, locators) moves in the reconstructed armature exactly like it
    moves in Blender.

    :param pose_bone: the pose bone of an imported bone.
    :returns: the reconstructed transformation or ``None`` when the bone
        wasn't created by the importer.
    '''
    original_rest = get_imported_rest(pose_bone)
    if original_rest is None:
        return None
    actual_rest = pose_bone.bone.matrix_local
    correction = actual_rest.inverted_safe() @ original_rest
    return pose_bone.matrix @ correction


def imported_obj_matrix(objprop: 'McblendObject') -> Optional[Matrix]:
    '''
    The :attr:`McblendObject.obj_matrix_world` of an imported bone - the
    object matrix computed from the original (pre-import) rest transformation
    of the bone and its current pose.

    :param objprop: the object properties of a bone.
    :returns: the reconstructed object matrix or ``None`` when the object is
        not a bone created by the importer (in that case the normal
        transformation of the object should be used).
    '''
    if objprop.thisobj.type != 'ARMATURE':
        return None
    if objprop.thisobj_id.bone_name == '':
        return None
    return imported_pose_matrix(objprop.this_pose_bone)


# ---------------------------------------------------------------------------
# Building the logical skeleton
# ---------------------------------------------------------------------------
def _to_blender_point(mc: Any) -> Vector:
    '''Minecraft coordinates -> Blender coordinates.'''
    from mcblend.operator_func.common import MINECRAFT_SCALE_FACTOR
    return Vector((mc[0], mc[2], mc[1])) / MINECRAFT_SCALE_FACTOR


def _mc_rotation(mcrotation: Any) -> Matrix:
    '''Minecraft rotation -> rotation matrix (Blender coordinates).'''
    return Euler((
        math.radians(mcrotation[0]),
        math.radians(mcrotation[2]),
        math.radians(-mcrotation[1]),
    ), 'XZY').to_matrix()


def _geometry_direction(
        bone: 'ImportBone', epsilon: float) -> Optional[Vector]:
    '''
    The direction (and the reach) of the geometry that the bone owns.

    The returned vector starts in the pivot point of the bone and points at
    the point of the cubes of the bone that is the furthest away from it. The
    world transformation of the empty object of the bone maps the points of
    the model (in the Blender coordinates) onto the observed skeleton - it's
    the very same transformation that the cubes of the bone have in the
    imported armature (see the importer).

    :param bone: the imported bone with the reference to its empty object.
    :param epsilon: the minimal length of the geometry.
    :returns: the vector or ``None`` when the bone has no cubes.
    '''
    if bone.blend_empty is None or not bone.cubes:
        return None

    to_observed = bone.blend_empty.matrix_world.to_3x3()
    pivot = _to_blender_point(bone.pivot)
    far: Optional[Vector] = None
    for cube in bone.cubes:
        cube_pivot = _to_blender_point(cube.pivot)
        rotation = _mc_rotation(cube.rotation or (0.0, 0.0, 0.0))
        mc_origin = cube.origin
        mc_size = cube.size
        for x in (0.0, mc_size[0]):
            for y in (0.0, mc_size[1]):
                for z in (0.0, mc_size[2]):
                    corner = _to_blender_point((
                        mc_origin[0] + x,
                        mc_origin[1] + y,
                        mc_origin[2] + z,
                    ))
                    # The cube is rotated around its own pivot point and the
                    # whole bone is rotated with the transformation of its
                    # empty object.
                    corner = cube_pivot + rotation @ (corner - cube_pivot)
                    offset = to_observed @ (corner - pivot)
                    if far is None or offset.length > far.length:
                        far = offset
    if far is None or far.length <= epsilon:
        return None
    return far


def compute_bone_shapes(
        bones: Dict[str, 'ImportBone'],
        epsilon: float = 1e-4,
        leaf_length: float = 0.3
) -> Dict[str, Tuple['Vector3d', 'Vector3d']]:
    '''
    Computes the ``head`` and ``tail`` (in the armature space) of every
    imported bone so that the created armature forms a logical skeleton
    instead of a set of identical stubs pointing in the same direction.

    Every bone starts in its own pivot point. The bones that own some
    geometry (cubes) point along that geometry so that the bone - and with it
    the physics simulation created by Mcblend - covers the part of the model
    that the bone controls.

    A bone ends in the pivot point of the child that continues it (the child
    that lies along the geometry of the bone and in its scale) so that the
    chain of the bones still meets in the joints of the model (the bones that
    meet in a joint are connected, see
    :func:`mcblend.operator_func.importer.ModelLoader.build_with_armature`).
    When no child continues the bone, it ends in its own geometry (it is as
    long as the geometry that it owns).

    The bones without any geometry (they serve only as the joints of the
    skeleton) keep the original behaviour: they point at the furthest child
    or, when they have no children, away from their parent.

    :param bones: the imported bones (keyed by their names) with references
        to the Blender objects that represent them.
    :param epsilon: the minimal distance between two pivot points that is
        treated as a non-zero length.
    :param leaf_length: the length of the bones that have no children with a
        different pivot point.
    :returns: dictionary that maps the name of a bone to a tuple with the
        head and the tail position of the bone.
    '''
    # Pivot point of every bone (in the Blender space)
    pivots: Dict[str, Vector] = {}
    for name, bone in bones.items():
        if bone.blend_empty is None:
            raise ImporterException(
                f'Bone "{name}" has no Blender representation.')
        pivots[name] = Vector(bone.blend_empty.matrix_world.translation)

    # Children of every bone
    children: Dict[str, List[str]] = {name: [] for name in bones}
    for name, bone in bones.items():
        if bone.parent is not None and bone.parent in bones:
            children[bone.parent].append(name)

    result: Dict[str, Tuple['Vector3d', 'Vector3d']] = {}
    for name, bone in bones.items():
        head = pivots[name]
        tail: Optional[Vector] = None

        # 1. Bones that own some geometry point along it. The tail is put in
        # the pivot point of the child that continues the bone (it lies along
        # the geometry of the bone and in its scale).
        geometry = _geometry_direction(bone, epsilon)
        if geometry is not None:
            geometry_direction = geometry.normalized()
            best: Optional[str] = None
            best_dot = 0.5  # the child has to lie within 60 degrees
            best_length = 0.0
            for child_name in children[name]:
                offset = pivots[child_name] - head
                length = offset.length
                if length <= epsilon:
                    continue
                # The child has to be in the scale of the geometry of this
                # bone - a bone doesn't continue in a child that is way
                # smaller (it would produce a degenerate bone) or way bigger
                # (it would produce an absurdly long bone, e.g. for the bones
                # that are used as the reference points of the model).
                if not (
                        0.3 * geometry.length <= length
                        <= 2.5 * geometry.length):
                    continue
                dot = offset.normalized().dot(geometry_direction)
                if (dot > best_dot + 1e-6
                        or (dot > best_dot - 1e-6
                            and (best is None
                                 or length < best_length))):
                    best, best_dot, best_length = child_name, dot, length
            if best is not None:
                tail = pivots[best]
            else:
                tail = head + geometry

        # 2. Bones without any geometry point at the furthest child.
        if tail is None:
            furthest = epsilon
            for child_name in children[name]:
                dist = (pivots[child_name] - head).length
                if dist > furthest:
                    furthest = dist
                    tail = pivots[child_name]

        # 3. Leaf bones (and bones whose children share the same pivot point)
        # point away from their parent.
        if tail is None:
            if bone.parent is not None and bone.parent in pivots:
                direction = head - pivots[bone.parent]
                if direction.length > epsilon:
                    tail = head + direction.normalized() * leaf_length
            if tail is None:
                tail = head + Vector((0.0, 0.0, leaf_length))

        result[name] = (
            (head.x, head.y, head.z),
            (tail.x, tail.y, tail.z),
        )
    return result
