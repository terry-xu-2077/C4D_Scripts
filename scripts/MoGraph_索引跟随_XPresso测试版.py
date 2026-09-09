# -*- coding: utf-8 -*-
"""
MoGraph 索引跟随 - XPresso 测试版
================================

目的：解决普通 Python Tag 在手动拖动时间轴播放头（scrub）时，
MoData/执行管线刷新不稳定导致目标对象回到自身动画位置的问题。

本版本由 Python 脚本负责一次性搭建表达式，但运行时不再由 Python Tag
直接读取 MoData，而是使用 Cinema 4D 原生 XPresso「Motion Graphics Data」
节点读取指定克隆的 Global Matrix。

使用：
1. 选择一个分裂 / 克隆 / 矩阵对象。
2. 运行本脚本。
3. 在该 MoGraph 对象的用户数据中设置：
   - 对象索引
   - 被链接对象
   - 过渡
4. 测试连续播放以及手动拖动时间轴播放头。

注意：
- 这是用于验证 scrub 问题的测试版，不会覆盖旧的 Python Tag 版本。
- 用户数据暂时放在 MoGraph 对象本身，避免运行时 Python 参与表达式求值。
"""

import c4d


TAG_NAME = "MoGraph 索引跟随 [XPresso]"
VALID_TYPES = (c4d.Omgfracture, c4d.Omgcloner, c4d.Omgmatrix)
MG_DATA_OPERATOR_ID = getattr(c4d, "ID_OPERATOR_MG_DATA", 1019010)


def add_group_userdata(node, name):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME] = name
    return node.AddUserData(bc)


def add_long_userdata(node, name, parent, default=0, minimum=0):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = int(default)
    bc[c4d.DESC_MIN] = int(minimum)
    bc[c4d.DESC_MINSLIDER] = int(minimum)
    bc[c4d.DESC_STEP] = 1
    bc[c4d.DESC_PARENTGROUP] = parent
    did = node.AddUserData(bc)
    node[did] = int(default)
    return did


def add_link_userdata(node, name, parent):
    bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_BASELISTLINK)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_PARENTGROUP] = parent
    did = node.AddUserData(bc)
    node[did] = None
    return did


def add_percent_userdata(node, name, parent, default=1.0):
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
    bc[c4d.DESC_PARENTGROUP] = parent
    did = node.AddUserData(bc)
    node[did] = float(default)
    return did


def add_port(node, io, port_id):
    """返回已有端口；没有时则创建。port_id 可以是 int 或 DescID。"""
    ports = node.GetInPorts() if io == c4d.GV_PORT_INPUT else node.GetOutPorts()

    target_id = None
    if isinstance(port_id, c4d.DescID):
        target_id = port_id
    else:
        target_id = int(port_id)

    for port in ports:
        try:
            if isinstance(target_id, c4d.DescID):
                # 用户数据端口用 DescID 比较。
                if port.GetMainID() == target_id[0].id:
                    # GetMainID 对用户数据不总能唯一识别，因此已有端口时优先复用，
                    # 后续新建脚本通常不会有重复用户数据端口。
                    pass
            else:
                if port.GetMainID() == target_id:
                    return port
        except Exception:
            pass

    port = node.AddPort(io, port_id, c4d.GV_PORT_FLAG_IS_VISIBLE)
    if port is None:
        raise RuntimeError("无法创建 XPresso 端口: %r" % (port_id,))
    return port


def connect(out_port, in_port, label):
    if out_port is None or in_port is None or not out_port.Connect(in_port):
        raise RuntimeError("无法连接 XPresso：%s" % label)


def create_graph(source, index_did, target_did, blend_did):
    tag = c4d.BaseTag(c4d.Texpresso)
    if tag is None:
        raise MemoryError("无法创建 XPresso Tag。")

    tag.SetName(TAG_NAME)
    source.InsertTag(tag)

    master = tag.GetNodeMaster()
    root = master.GetRoot()
    if master is None or root is None:
        raise RuntimeError("无法取得 XPresso NodeMaster。")

    # 1) 控制/源对象节点：输出源对象本身 + 三个用户数据。
    src_node = master.CreateNode(root, c4d.ID_OPERATOR_OBJECT, x=20, y=80)
    src_node[c4d.GV_OBJECT_OBJECT_ID] = source
    src_node.SetName("MoGraph / 控制")

    src_object_out = add_port(src_node, c4d.GV_PORT_OUTPUT, c4d.GV_OBJECT_OPERATOR_OBJECT_OUT)
    src_index_out = add_port(src_node, c4d.GV_PORT_OUTPUT, index_did)
    src_target_out = add_port(src_node, c4d.GV_PORT_OUTPUT, target_did)
    src_blend_out = add_port(src_node, c4d.GV_PORT_OUTPUT, blend_did)

    # 2) 原生 Motion Graphics Data 节点。
    mg_node = master.CreateNode(root, MG_DATA_OPERATOR_ID, x=270, y=20)
    if mg_node is None:
        raise RuntimeError("无法创建 Motion Graphics Data 节点。")
    mg_node.SetName("MoGraph Data")

    mg_index_in = add_port(mg_node, c4d.GV_PORT_INPUT, c4d.GV_MG_DATA_INDEX)
    mg_object_in = add_port(mg_node, c4d.GV_PORT_INPUT, c4d.GV_MG_DATA_OBJECT)
    mg_global_out = add_port(mg_node, c4d.GV_PORT_OUTPUT, c4d.GV_MG_DATA_OGMATRIX)

    connect(src_index_out, mg_index_in, "对象索引 -> MoGraph Data")
    connect(src_object_out, mg_object_in, "MoGraph 对象 -> MoGraph Data")

    # 3) 目标读取节点。单独使用一个 Object 节点读取目标当前动画结果，
    # 再用另一个 Object 节点写入，避免图结构自身形成节点环。
    target_read = master.CreateNode(root, c4d.ID_OPERATOR_OBJECT, x=270, y=230)
    target_read.SetName("目标 / 读取动画")
    target_read_obj_in = add_port(target_read, c4d.GV_PORT_INPUT, c4d.GV_OBJECT_OPERATOR_OBJECT_IN)
    target_global_out = add_port(target_read, c4d.GV_PORT_OUTPUT, c4d.GV_OBJECT_OPERATOR_GLOBAL_OUT)

    target_write = master.CreateNode(root, c4d.ID_OPERATOR_OBJECT, x=790, y=140)
    target_write.SetName("目标 / 写入结果")
    target_write_obj_in = add_port(target_write, c4d.GV_PORT_INPUT, c4d.GV_OBJECT_OPERATOR_OBJECT_IN)
    target_global_in = add_port(target_write, c4d.GV_PORT_INPUT, c4d.GV_OBJECT_OPERATOR_GLOBAL_IN)

    connect(src_target_out, target_read_obj_in, "被链接对象 -> 目标读取")
    connect(src_target_out, target_write_obj_in, "被链接对象 -> 目标写入")

    # 4) Matrix Mix：0% = 目标对象当前动画矩阵，100% = MoGraph Global Matrix。
    mix_node = master.CreateNode(root, c4d.ID_OPERATOR_MIX, x=540, y=130)
    if mix_node is None:
        raise RuntimeError("无法创建 Mix 节点。")
    mix_node.SetName("过渡")
    mix_node[c4d.GV_DYNAMIC_DATATYPE] = c4d.ID_GV_DATA_TYPE_MATRIX

    mix_a = add_port(mix_node, c4d.GV_PORT_INPUT, c4d.GV_MIX_INPUT1)
    mix_b = add_port(mix_node, c4d.GV_PORT_INPUT, c4d.GV_MIX_INPUT2)
    mix_factor = add_port(mix_node, c4d.GV_PORT_INPUT, c4d.GV_MIX_INPUT_MIXINGFACTOR)
    mix_out = add_port(mix_node, c4d.GV_PORT_OUTPUT, c4d.GV_MIX_OUTPUT)

    connect(target_global_out, mix_a, "目标动画矩阵 -> Mix A")
    connect(mg_global_out, mix_b, "MoGraph Global Matrix -> Mix B")
    connect(src_blend_out, mix_factor, "过渡 -> Mix Factor")
    connect(mix_out, target_global_in, "Mix -> 目标 Global Matrix")

    # MoGraph Data 需要在生成器阶段读取最终结果。
    priority = tag[c4d.EXPRESSION_PRIORITY]
    if isinstance(priority, c4d.PriorityData):
        priority.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_GENERATORS)
        priority.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, 499)
        priority.SetPriorityValue(c4d.PRIORITYVALUE_CAMERADEPENDENT, False)
        tag[c4d.EXPRESSION_PRIORITY] = priority

    return tag


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
        group = add_group_userdata(source, "MoGraph 索引跟随")
        index_did = add_long_userdata(source, "对象索引", group, 0, 0)
        target_did = add_link_userdata(source, "被链接对象", group)
        blend_did = add_percent_userdata(source, "过渡", group, 1.0)

        tag = create_graph(source, index_did, target_did, blend_did)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
        doc.SetActiveTag(tag)
    except Exception as exc:
        c4d.gui.MessageDialog("创建失败：\n%s" % exc)
        raise
    finally:
        doc.EndUndo()

    c4d.EventAdd()


if __name__ == "__main__":
    main()
