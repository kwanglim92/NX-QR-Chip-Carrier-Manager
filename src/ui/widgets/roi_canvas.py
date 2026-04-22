"""ROI 시각적 편집 캔버스 — QGraphicsView 기반 (F-14 Calibrator용).

이미지 위에 두 개의 라벨링된 직사각형(``frequency``, ``q_factor``)을 올려
드래그로 이동·크기 조절하고, 외부 QSpinBox 와 양방향 동기화한다.

- ``RoiRectItem`` : 하나의 ROI 박스. ``ItemIsMovable`` + 우하단 리사이즈 핸들.
- ``RoiCanvas`` : 이미지 + RoiRectItem 2개를 담는 뷰.
- 좌표는 항상 **이미지 픽셀 단위** (씬 좌표계) — 뷰 확대/축소와 무관.

Signals
-------
``RoiCanvas.roi_changed(name: str, rect: tuple[int,int,int,int])``
    박스가 이동·리사이즈될 때마다 방출. 외부 위젯은 이를 받아 QSpinBox 값 갱신.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from src.ui.theme import ACCENT, ORANGE, GREEN, BG

# ROI 이름별 색상 (가시성 확보)
ROI_COLORS = {
    "frequency": QColor(ACCENT),
    "q_factor": QColor(ORANGE),
}

HANDLE_SIZE = 10  # 리사이즈 핸들 픽셀 크기 (씬 좌표)


class _ResizeHandle(QGraphicsRectItem):
    """부모 RoiRectItem 의 우하단에 붙는 리사이즈 핸들.

    드래그 중 부모 사각형의 너비/높이를 갱신하고 ``RoiRectItem._emit_change`` 호출.
    """

    def __init__(self, parent: "RoiRectItem"):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, parent)
        self._parent_roi = parent
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.setBrush(QBrush(QColor(GREEN)))
        self.setPen(QPen(QColor(BG), 1))
        self.setCursor(QCursor(Qt.SizeFDiagCursor))
        self.setZValue(2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos: QPointF = value
            rect = self._parent_roi.rect()
            # 핸들은 부모 좌표계에서 (w, h) 위치 — 이 위치를 새 w/h로 해석
            # 최소 크기 10×10 보장
            new_w = max(10.0, new_pos.x())
            new_h = max(10.0, new_pos.y())
            self._parent_roi.setRect(QRectF(0, 0, new_w, new_h))
            self._parent_roi._refresh_label_pos()
            self._parent_roi._emit_change()
            # 핸들 위치는 (new_w, new_h) 로 snap
            return QPointF(new_w, new_h)
        return super().itemChange(change, value)


class RoiRectItem(QGraphicsRectItem):
    """단일 ROI 직사각형 + 이름 라벨 + 우하단 리사이즈 핸들."""

    def __init__(self, name: str, rect: tuple[int, int, int, int], canvas: "RoiCanvas"):
        x, y, w, h = rect
        super().__init__(0, 0, w, h)
        self.name = name
        self._canvas = canvas
        self.setPos(x, y)

        color = ROI_COLORS.get(name, QColor(ACCENT))
        pen = QPen(color, 2)
        pen.setCosmetic(True)  # 뷰 확대해도 선 두께 일정
        self.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(40)
        self.setBrush(QBrush(fill))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(QCursor(Qt.SizeAllCursor))
        self.setZValue(1)

        # 이름 라벨 (박스 좌상단 바로 위)
        self._label = QGraphicsSimpleTextItem(name, self)
        self._label.setBrush(QBrush(color))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        self._label.setFont(font)
        self._refresh_label_pos()

        # 리사이즈 핸들 (우하단)
        self._handle = _ResizeHandle(self)
        self._handle.setPos(w, h)

    def _refresh_label_pos(self) -> None:
        self._label.setPos(0, -16)

    def _emit_change(self) -> None:
        self._canvas.roi_changed.emit(self.name, self.roi_tuple())

    def roi_tuple(self) -> tuple[int, int, int, int]:
        """현재 ROI를 (x, y, w, h) 정수 픽셀로 반환."""
        pos = self.pos()
        rect = self.rect()
        return int(pos.x()), int(pos.y()), int(rect.width()), int(rect.height())

    def set_roi_tuple(self, x: int, y: int, w: int, h: int) -> None:
        """외부에서 ROI 값을 세팅 (QSpinBox → Canvas 방향 동기화용)."""
        self.setRect(QRectF(0, 0, max(10, w), max(10, h)))
        self.setPos(x, y)
        self._handle.setPos(max(10, w), max(10, h))
        self._refresh_label_pos()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._emit_change()
        return super().itemChange(change, value)


class RoiCanvas(QGraphicsView):
    """이미지 + 두 개의 RoiRectItem(frequency, q_factor)을 담는 편집 캔버스."""

    roi_changed = Signal(str, tuple)  # name, (x, y, w, h)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"background: {BG};")

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._roi_items: dict[str, RoiRectItem] = {}
        self._image_size: tuple[int, int] = (0, 0)

    # ─── 이미지 로드 ───

    def load_image(self, path: str) -> bool:
        """이미지 로드. 성공 시 True. 실패 시 씬 클리어하고 False."""
        self._scene.clear()
        self._pixmap_item = None
        self._roi_items.clear()

        pm = QPixmap(path)
        if pm.isNull():
            self._image_size = (0, 0)
            return False

        self._pixmap_item = self._scene.addPixmap(pm)
        self._pixmap_item.setZValue(0)
        self._image_size = (pm.width(), pm.height())
        self._scene.setSceneRect(0, 0, pm.width(), pm.height())
        self._fit()
        return True

    def image_size(self) -> tuple[int, int]:
        return self._image_size

    def _fit(self) -> None:
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    # ─── ROI 항목 관리 ───

    def set_rois(self, roi: dict[str, tuple[int, int, int, int]]) -> None:
        """기존 ROI 항목을 모두 제거하고 새 dict 로 재구성."""
        # 기존 제거
        for item in list(self._roi_items.values()):
            self._scene.removeItem(item)
        self._roi_items.clear()

        for name, rect in roi.items():
            item = RoiRectItem(name, rect, self)
            self._scene.addItem(item)
            self._roi_items[name] = item

    def update_roi(self, name: str, rect: tuple[int, int, int, int]) -> None:
        """외부(QSpinBox)로부터 값을 받아 해당 박스 갱신 (시그널 재방출 없음)."""
        item = self._roi_items.get(name)
        if item is None:
            return
        x, y, w, h = rect
        # 갱신 중 자체 시그널 재방출을 막기 위해 블로킹
        self.blockSignals(True)
        try:
            item.set_roi_tuple(x, y, w, h)
        finally:
            self.blockSignals(False)

    def current_rois(self) -> dict[str, tuple[int, int, int, int]]:
        return {name: item.roi_tuple() for name, item in self._roi_items.items()}
