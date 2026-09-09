# -*- coding: utf-8 -*-
"""
MoGraph 索引跟随
==============

用法：
1. 在 Cinema 4D 中选择一个 MoGraph 生成器（分裂 / 克隆 / 矩阵对象）。
2. 运行本脚本。
3. 脚本会在所选对象上创建一个 Python Tag，并添加：
   - 对象索引：要读取的 MoData 元素索引（从 0 开始）
   - 被链接对象：接收世界变换的对象
   - 过渡：0% 为被链接对象在首次链接时的初始世界变换，100% 为 MoGraph 元素的最终世界变换

说明：
- 读取 MODATA_MATRIX，即经过 MoGraph 效果器计算后的矩阵。
- 世界矩阵 = MoGraph 生成器世界矩阵 * MODATA_MATRIX[index]。
- Python Tag 设置到 Generators 优先级较后阶段，以尽量读取最终 MoGraph 结果。
"""

import c4d


TAG_NAME = "MoGraph 索引跟随"
VALID_TYPES = (c4d.Omgfracture, c4d.Omgcloner, c4d.Omgmatrix)


def _add_long_userdata(node, name, default=0, minimum=0):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = int(default)
    bc[c4d.DESC_MIN] = int(minimum)
    bc[c4d.DESC_MINSLIDER] = int(minimum)
    bc[c4d.DESC_STEP] = 1

    desc_id = node.AddUserData(bc)
    node[desc_id] = int(default)
    return desc_id


def _add_link_userdata(node, name):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
    bc[c4d.DESC_NAME] = name

    desc_id = node.AddUserData(bc)
    node[desc_id] = None
    return desc_id


def _add_percent_userdata(node, name, default=1.0):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = float(default)
    bc[c4d.DESC_MIN] = 0.0
    bc[c4d.DESC_MAX] = 1.0
    bc[c4d.DESC_MINSLIDER] = 0.0
    bc[c4d.DESC_MAXSLIDER] = 1.0
    bc[c4d.DESC_STEP] = 0.01
    bc[c4d.DESC_UNIT] = c4d.DESC_UNIT_PERCENT
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER

    desc_id = node.AddUserData(bc)
    node[desc_id] = float(default)
    return desc_id


def _userdata_index(desc_id):
    """从 [ID_USERDATA, x] DescID 中取出 x。"""
    return desc_id[1].id


def _build_tag_code(index_id, target_id, blend_id):
    return f'''# -*- coding: utf-8 -*-
import c4d
from c4d import utils
from c4d.modules import mograph

# 此三个 ID 由安装脚本创建用户数据后自动写入。
UD_INDEX = {index_id}
UD_TARGET = {target_id}
UD_BLEND = {blend_id}

# Python Tag 内部缓存。使用普通 BaseContainer ID，不显示在用户数据里。
CACHE_TARGET = 1061001
CACHE_BASE_MATRIX = 1061002
CACHE_VALID = 1061003

_EPS = 1.0e-10


def get_modata(source):
    # 读取 MoGraph 数据；优先直接读取对象，必要时回退到缓存。
    if source is None:
        return None

    md = mograph.GeGetMoData(source)
    if md is not None:
        return md

    cache = source.GetCache()
    if cache is not None:
        md = mograph.GeGetMoData(cache)
        if md is not None:
            return md

    deform_cache = source.GetDeformCache()
    if deform_cache is not None:
        md = mograph.GeGetMoData(deform_cache)
        if md is not None:
            return md

    return None


def decompose_matrix(m):
    # 将矩阵拆为世界位置、HPB 旋转和缩放。常规 MoGraph TRS 有效，不保留剪切。
    pos = c4d.Vector(m.off)

    sx = m.v1.GetLength()
    sy = m.v2.GetLength()
    sz = m.v3.GetLength()

    # 避免零缩放导致除零。
    nx = m.v1 / sx if sx > _EPS else c4d.Vector(1.0, 0.0, 0.0)
    ny = m.v2 / sy if sy > _EPS else c4d.Vector(0.0, 1.0, 0.0)
    nz = m.v3 / sz if sz > _EPS else c4d.Vector(0.0, 0.0, 1.0)

    rot_m = c4d.Matrix(off=c4d.Vector(0.0), v1=nx, v2=ny, v3=nz)
    rot = utils.MatrixToHPB(rot_m, c4d.ROTATIONORDER_DEFAULT, True)
    scale = c4d.Vector(sx, sy, sz)
    return pos, rot, scale


def compose_matrix(pos, rot, scale):
    # 由位置、HPB 旋转和缩放重新构建矩阵。
    m = utils.HPBToMatrix(rot, c4d.ROTATIONORDER_DEFAULT)
    m.off = c4d.Vector(pos)
    m.v1 *= scale.x
    m.v2 *= scale.y
    m.v3 *= scale.z
    return m


def blend_matrix(a, b, t):
    # 分别插值位置、旋转、缩放。
    if t <= 0.0:
        return c4d.Matrix(a)
    if t >= 1.0:
        return c4d.Matrix(b)

    pos_a, rot_a, scale_a = decompose_matrix(a)
    pos_b, rot_b, scale_b = decompose_matrix(b)

    # 选择离起始旋转最近的等价 HPB，减少跨 ±180° 时的翻转。
    rot_b = utils.GetOptimalAngle(
        rot_a, rot_b, c4d.ROTATIONORDER_DEFAULT
    )

    pos = utils.MixVec(pos_a, pos_b, t)
    rot = utils.MixVec(rot_a, rot_b, t)
    scale = utils.MixVec(scale_a, scale_b, t)
    return compose_matrix(pos, rot, scale)


def get_or_store_base_matrix(tag, target):
    # 第一次链接某对象时记录其世界矩阵；重新指定被链接对象时重新记录。
    bc = tag.GetDataInstance()
    cached_target = bc.GetLink(CACHE_TARGET, doc)
    valid = bc.GetBool(CACHE_VALID)

    if (not valid) or cached_target != target:
        bc.SetLink(CACHE_TARGET, target)
        bc.SetMatrix(CACHE_BASE_MATRIX, target.GetMg())
        bc.SetBool(CACHE_VALID, True)

    return bc.GetMatrix(CACHE_BASE_MATRIX)


def main():
    source = op.GetObject()
    if source is None:
        return

    index = int(op[c4d.ID_USERDATA, UD_INDEX])
    target = op[c4d.ID_USERDATA, UD_TARGET]
    blend = float(op[c4d.ID_USERDATA, UD_BLEND])

    if not isinstance(target, c4d.BaseObject):
        return

    # 避免最直接的自引用。
    if target == source:
        return

    md = get_modata(source)
    if md is None:
        return

    matrices = md.GetArray(c4d.MODATA_MATRIX)
    if not matrices:
        return

    # 自动限制索引，防止克隆数量变化后越界。
    index = max(0, min(index, len(matrices) - 1))
    local_clone_mg = matrices[index]

    # 官方 MoGraph 逻辑：全局克隆矩阵 = 生成器 Mg * MODATA_MATRIX。
    generator = md.GetGenerator()
    generator_mg = generator.GetMg() if isinstance(generator, c4d.BaseObject) else source.GetMg()
    clone_world_mg = generator_mg * local_clone_mg

    base_world_mg = get_or_store_base_matrix(op, target)
    blend = max(0.0, min(blend, 1.0))

    result_mg = blend_matrix(base_world_mg, clone_world_mg, blend)
    target.SetMg(result_mg)
'''


def main():
    doc = c4d.documents.GetActiveDocument()
    source = doc.GetActiveObject()

    if source is None:
        c4d.gui.MessageDialog("请先选择一个分裂、克隆或矩阵对象。")
        return

    if source.GetType() not in VALID_TYPES:
        c4d.gui.MessageDialog("当前对象不是分裂、克隆或矩阵对象。")
        return

    doc.StartUndo()
    try:
        tag = c4d.BaseTag(c4d.Tpython)
        if tag is None:
            raise MemoryError("无法创建 Python Tag。")

        tag.SetName(TAG_NAME)
        source.InsertTag(tag)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)

        index_desc = _add_long_userdata(tag, "对象索引", default=0, minimum=0)
        target_desc = _add_link_userdata(tag, "被链接对象")
        blend_desc = _add_percent_userdata(tag, "过渡", default=1.0)

        tag[c4d.TPYTHON_CODE] = _build_tag_code(
            _userdata_index(index_desc),
            _userdata_index(target_desc),
            _userdata_index(blend_desc),
        )
        tag[c4d.TPYTHON_FRAME] = True

        # 放到生成器阶段靠后执行，从而尽量读取已经过效果器计算的 MoData。
        priority = tag[c4d.EXPRESSION_PRIORITY]
        if isinstance(priority, c4d.PriorityData):
            priority.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_GENERATORS)
            priority.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, 499)
            priority.SetPriorityValue(c4d.PRIORITYVALUE_CAMERADEPENDENT, False)
            tag[c4d.EXPRESSION_PRIORITY] = priority

        tag.Message(c4d.MSG_MENUPREPARE)
        doc.SetActiveTag(tag)
    finally:
        doc.EndUndo()

    c4d.EventAdd()


if __name__ == "__main__":
    main()
