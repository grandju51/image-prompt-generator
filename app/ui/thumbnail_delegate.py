from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from app.constants import ItemStatus, THUMBNAIL_SIZE

_STATUS_COLORS = {
    ItemStatus.PENDING: QColor("#777777"),
    ItemStatus.PROCESSING: QColor("#4A90E2"),
    ItemStatus.DONE: QColor("#5CB85C"),
    ItemStatus.FAILED: QColor("#D9534F"),
}
_DOT_SIZE = 10
_PAD = 6


class ThumbnailDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        item = index.data(Qt.ItemDataRole.UserRole)
        if item is None:
            super().paint(painter, option, index)
            return

        painter.save()
        r = option.rect

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(r, option.palette.highlight() if selected else option.palette.base())

        # Thumbnail area
        thumb_x = r.x() + _PAD
        thumb_y = r.y() + _PAD
        thumb_rect = QRect(thumb_x, thumb_y, THUMBNAIL_SIZE, THUMBNAIL_SIZE)

        if item.thumbnail and not item.thumbnail.isNull():
            scaled = item.thumbnail.scaled(
                THUMBNAIL_SIZE, THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = thumb_rect.x() + (THUMBNAIL_SIZE - scaled.width()) // 2
            oy = thumb_rect.y() + (THUMBNAIL_SIZE - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)
        else:
            painter.fillRect(thumb_rect, QColor("#444444"))

        # Filename text
        text_x = thumb_x + THUMBNAIL_SIZE + _PAD
        dot_space = _DOT_SIZE + _PAD * 2
        text_w = r.right() - text_x - dot_space
        text_rect = QRect(text_x, r.y() + _PAD, text_w, r.height() - _PAD * 2)

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        pen_color = option.palette.highlightedText().color() if selected else option.palette.text().color()
        painter.setPen(pen_color)

        fm = painter.fontMetrics()
        elided = fm.elidedText(item.path.name, Qt.TextElideMode.ElideMiddle, text_w)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # File type tag
        tag = "IMG" if item.file_type.value == "image" else "VID"
        tag_font = QFont()
        tag_font.setPointSize(7)
        painter.setFont(tag_font)
        tag_y = text_rect.y() + fm.height() + 2
        painter.setPen(QColor("#888888"))
        painter.drawText(QRect(text_x, tag_y, text_w, 16),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tag)

        # Status dot
        status = item.status if hasattr(item, "status") else ItemStatus.PENDING
        dot_color = _STATUS_COLORS.get(status, QColor("#777777"))
        dot_x = r.right() - _PAD - _DOT_SIZE
        dot_y = r.y() + (r.height() - _DOT_SIZE) // 2
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_x, dot_y, _DOT_SIZE, _DOT_SIZE)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(260, THUMBNAIL_SIZE + _PAD * 2)
