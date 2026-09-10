import c4d
import random
import colorsys


# ============================================================
# 选中材质随机彩色
# Cinema 4D 2025
#
# 功能：
# - 读取材质管理器中当前选中的多个材质
# - 仅处理 Cinema 4D 标准/默认渲染器材质（Mmaterial）
# - 为每个材质生成不重复、彼此尽量分离的随机彩色
# - 只修改“颜色”通道，不删除贴图、不修改其它材质参数
# - 支持 Cinema 4D Undo
# ============================================================


# 彩色范围。
# 饱和度和值保持在较高区间，避免生成灰色、黑色或过脏的颜色。
SATURATION_MIN = 0.58
SATURATION_MAX = 0.88

VALUE_MIN = 0.72
VALUE_MAX = 1.00


def generate_unique_colors(count):
    """生成 count 个不重复且色相尽量分散的 RGB 颜色。"""
    if count <= 0:
        return []

    # 随机起始色相 + 等距色相分布。
    # 相比完全随机，这样既保留随机性，又能避免多个材质抽到非常接近的颜色。
    hue_offset = random.random()

    hues = [
        (hue_offset + (float(i) / float(count))) % 1.0
        for i in range(count)
    ]

    # 打乱材质最终获得色相的顺序。
    random.shuffle(hues)

    colors = []

    for hue in hues:
        saturation = random.uniform(SATURATION_MIN, SATURATION_MAX)
        value = random.uniform(VALUE_MIN, VALUE_MAX)

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append(c4d.Vector(r, g, b))

    return colors


def main():
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return

    selected_materials = doc.GetActiveMaterials()

    if not selected_materials:
        c4d.gui.MessageDialog(
            "请先在材质管理器中选中一个或多个 C4D 标准材质。"
        )
        return

    # 只处理 Cinema 4D 标准材质。
    standard_materials = [
        mat for mat in selected_materials
        if mat is not None and mat.IsInstanceOf(c4d.Mmaterial)
    ]

    skipped_count = len(selected_materials) - len(standard_materials)

    if not standard_materials:
        c4d.gui.MessageDialog(
            "当前选中的材质中没有 C4D 标准/默认渲染器材质。"
        )
        return

    colors = generate_unique_colors(len(standard_materials))

    doc.StartUndo()
    try:
        for mat, color in zip(standard_materials, colors):
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, mat)

            # 开启并修改标准材质的“颜色”通道。
            mat[c4d.MATERIAL_USE_COLOR] = True
            mat[c4d.MATERIAL_COLOR_COLOR] = color

            mat.Message(c4d.MSG_UPDATE)

    finally:
        doc.EndUndo()

    c4d.EventAdd()

    print(
        "[选中材质随机彩色] 已处理 {} 个标准材质，跳过 {} 个其它材质。".format(
            len(standard_materials),
            skipped_count
        )
    )


if __name__ == "__main__":
    main()
