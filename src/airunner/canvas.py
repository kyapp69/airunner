from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QCursor
from airunner.cursors.circle_brush import CircleCursor
from airunner.mixins.canvas_active_grid_area_mixin import CanvasActiveGridAreaMixin
from airunner.mixins.canvas_brushes_mixin import CanvasBrushesMixin
from airunner.mixins.canvas_grid_mixin import CanvasGridMixin
from airunner.mixins.canvas_image_mixin import CanvasImageMixin
from airunner.mixins.canvas_layer_mixin import CanvasLayerMixin
from airunner.mixins.canvas_selectionbox_mixin import CanvasSelectionboxMixin
from airunner.mixins.canvas_widgets_mixin import CanvasWidgetsMixin
from airunner.models.linedata import LineData


class Canvas(
    CanvasBrushesMixin,
    CanvasGridMixin,
    CanvasWidgetsMixin,
    CanvasImageMixin,
    CanvasSelectionboxMixin,
    CanvasActiveGridAreaMixin,
    CanvasLayerMixin,
):
    saving = False
    select_start = None
    select_end = None

    @property
    def current_layer(self):
        if len(self.layers) == 0:
            return None
        return self.layers[self.current_layer_index]

    @property
    def select_selected(self):
        return self.settings_manager.settings.current_tool.get() == "select"

    @property
    def eraser_selected(self):
        return self.settings_manager.settings.current_tool.get() == "eraser"

    @property
    def brush_selected(self):
        return self.settings_manager.settings.current_tool.get() == "brush"

    @property
    def move_selected(self):
        return self.settings_manager.settings.current_tool.get() == "move"

    @property
    def is_dragging(self):
        return False

    @property
    def is_zooming(self):
        return False

    @property
    def mouse_pos(self):
        return self.canvas_container.mapFromGlobal(QCursor.pos())

    @property
    def brush_size(self):
        return self.settings_manager.settings.mask_brush_size.get()

    @property
    def canvas_container(self):
        return self.parent.window.canvas_container

    @property
    def settings_manager(self):
        return self.parent.settings_manager

    @property
    def mouse_position(self):
        return self.canvas_container.mapFromGlobal(QCursor.pos())

    def __init__(
        self,
        parent=None
    ):
        self.canvas_rect = QRect(0, 0, 0, 0)
        self.pos_x = 0
        self.pos_y = 0
        self.current_layer_index = 0
        self.is_erasing = False
        self.start_drawing_line_index = 0
        self.stop_drawing_line_index = 0
        self.parent = parent
        self.image_pivot_point = QPoint(0, 0)
        self.image_root_point = QPoint(0, 0)

        CanvasGridMixin.initialize(self)
        CanvasActiveGridAreaMixin.initialize(self)
        CanvasLayerMixin.initialize(self)

        # Set initial position and size of the canvas
        self.canvas_container.setGeometry(QRect(
            int(self.canvas_rect.x()),
            int(self.canvas_rect.y()),
            int(self.canvas_rect.width()),
            int(self.canvas_rect.height())
        ))

        # set self.parent paintEvent
        self.canvas_container.paintEvent = self.paintEvent
        self.canvas_container.mousePressEvent = self.mouse_press_event
        self.canvas_container.mouseMoveEvent = self.mouse_move_event
        self.canvas_container.mouseReleaseEvent = self.mouse_release_event

        # on mouse hover
        self.canvas_container.enterEvent = self.enter_event
        self.canvas_container.leaveEvent = self.leave_event

        # Set the default brush color for drawing
        self.brush = QBrush()
        self.brush.setStyle(Qt.BrushStyle.SolidPattern)

        # Set the initial position for mouse dragging
        self.drag_pos = QPoint(0, 0)

        self.set_canvas_color()

    def handle_outpaint(self, outpaint_box_rect, outpainted_image, action):
        if len(self.current_layer.images) == 0:
            point = QPoint(outpaint_box_rect.x(), outpaint_box_rect.y())
            return outpainted_image, self.image_root_point, point

        # make a copy of the current canvas image
        existing_image_copy = self.current_layer.images[0].image.copy()
        width = existing_image_copy.width
        height = existing_image_copy.height
        working_width = self.settings_manager.settings.working_width.get()
        working_height = self.settings_manager.settings.working_height.get()

        is_drawing_left = outpaint_box_rect.x() < self.image_pivot_point.x()
        is_drawing_up = outpaint_box_rect.y() < self.image_pivot_point.y()

        if is_drawing_left:
            # get the x overlap of the outpaint box and the image
            x_overlap = min(width, outpaint_box_rect.width()) - max(0, outpaint_box_rect.x())
        else:
            # get the x overlap of the outpaint box and the image
            x_overlap = min(width, outpaint_box_rect.width()) - max(0, outpaint_box_rect.x() - self.image_pivot_point.x())

        if is_drawing_up:
            # get the y overlap of the outpaint box and the image
            y_overlap = min(height, outpaint_box_rect.height()) - max(0, outpaint_box_rect.y())
        else:
            # get the y overlap of the outpaint box and the image
            y_overlap = min(height, outpaint_box_rect.height()) - max(0, outpaint_box_rect.y() - self.image_pivot_point.y())

        # get the x and y overlap of the outpaint box and the image
        new_dimensions = (int(width + working_width - x_overlap), int(height + working_height - y_overlap))
        if new_dimensions[0] < width:
            new_dimensions = (width, new_dimensions[1])
        if new_dimensions[1] < height:
            new_dimensions = (new_dimensions[0], height)
        new_image = Image.new("RGBA", new_dimensions, (0, 0, 0, 0))
        new_image_a = Image.new("RGBA", new_dimensions, (0, 0, 0, 0))
        new_image_b = Image.new("RGBA", new_dimensions, (0, 0, 0, 0))
        existing_image_pos = [0, 0]
        image_root_point = QPoint(self.image_root_point.x(), self.image_root_point.y())
        image_pivot_point = QPoint(self.image_pivot_point.x(), self.image_pivot_point.y())
        if is_drawing_left:
            current_x_pos = abs(outpaint_box_rect.x() - image_pivot_point.x())
            left_overlap = abs(outpaint_box_rect.x()) - abs(image_root_point.x())
            image_root_point.setX(width + left_overlap)
            image_pivot_point.setX(int(outpaint_box_rect.x()))
            existing_image_pos = [current_x_pos, existing_image_pos[1]]
            pos_x = max(0, outpaint_box_rect.x() + self.image_pivot_point.x())
        else:
            pos_x = max(0, outpaint_box_rect.x() - self.image_pivot_point.x())
        if is_drawing_up:
            current_y_pos = abs(outpaint_box_rect.y() - image_pivot_point.y())
            up_overlap = abs(outpaint_box_rect.y()) - abs(image_root_point.y())
            image_root_point.setY(height + up_overlap)
            image_pivot_point.setY(int(outpaint_box_rect.y()))
            existing_image_pos = [existing_image_pos[0], current_y_pos]
            pos_y = max(0, outpaint_box_rect.y() + self.image_pivot_point.y())
        else:
            pos_y = max(0, outpaint_box_rect.y() - self.image_pivot_point.y())

        new_image_a.paste(outpainted_image, (int(pos_x), int(pos_y)))
        new_image_b.paste(existing_image_copy, (int(existing_image_pos[0]), int(existing_image_pos[1])))

        if action == "outpaint":
            new_image = Image.alpha_composite(new_image, new_image_a)
            new_image = Image.alpha_composite(new_image, new_image_b)
        else:
            new_image = Image.alpha_composite(new_image, new_image_b)
            new_image = Image.alpha_composite(new_image, new_image_a)

        return new_image, image_root_point, image_pivot_point

    def set_canvas_color(self):
        self.canvas_container.setStyleSheet(f"background-color: {self.settings_manager.settings.canvas_color.get()};")
        self.canvas_container.setAutoFillBackground(True)

    def paintEvent(self, event):
        CanvasGridMixin.paintEvent(self, event)
        layers = self.layers.copy()
        layers.reverse()
        for index in range(len(layers)):
            layer = layers[index]
            if not layer.visible:
                continue
            CanvasImageMixin.draw(self, layer, index)
            CanvasBrushesMixin.draw(self, layer, index)
            CanvasWidgetsMixin.draw(self, layer, index)
        CanvasSelectionboxMixin.paint_event(self, event)
        CanvasActiveGridAreaMixin.paint_event(self, event)

    def enter_event(self, event):
        self.update_cursor()

    def update_cursor(self):
        if self.brush_selected or self.eraser_selected:
            self.canvas_container.setCursor(CircleCursor(Qt.GlobalColor.white, Qt.GlobalColor.transparent, self.brush_size))
        elif self.move_selected:
            self.canvas_container.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.active_grid_area_selected:
            self.canvas_container.setCursor(Qt.CursorShape.DragMoveCursor)
        else:
            self.canvas_container.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def leave_event(self, event):
        self.canvas_container.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def update(self):
        self.canvas_container.update()

    def clear(self):
        self.current_layer.lines = []
        self.current_layer.images = []
        self.update()

    def recenter(self):
        self.pos_x = 0
        self.pos_y = 0
        self.update()

    def handle_move_canvas(self, event):
        self.pos_x += event.pos().x() - self.drag_pos.x()
        self.pos_y += event.pos().y() - self.drag_pos.y()
        self.drag_pos = event.pos()
        self.update()

    def handle_move_layer(self, event):
        point = QPoint(
            event.pos().x() if self.drag_pos is not None else 0,
            event.pos().y() if self.drag_pos is not None else 0
        )
        # snap to grid
        grid_size = self.settings_manager.settings.size.get()
        point.setX(point.x() - (point.x() % grid_size))
        point.setY(point.y() - (point.y() % grid_size))

        # center the image
        # point.setX(int((point.x() - self.current_layer.images[0].image.size[0] / 2)))
        # point.setY(int((point.y() - self.current_layer.images[0].image.size[1] / 2)))

        # establish a rect based on line points - we need the area that is being moved
        # so that we can center the point on it
        rect = QRect()
        for line in self.current_layer.lines:
            rect = rect.united(QRect(line.start_point, line.end_point))

        try:
            rect = rect.united(QRect(self.current_layer.images[0].position.x(), self.current_layer.images[0].position.y(), self.current_layer.images[0].image.size[0], self.current_layer.images[0].image.size[1]))
        except IndexError:
            pass

        # center the point on the rect
        point.setX(int(point.x() - int(rect.width() / 2)))
        point.setY(int(point.y() - int(rect.height() / 2)))

        self.layers[self.current_layer_index].offset = point

    def mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.select_start = event.pos()
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if self.brush_selected:
                self.parent.history.add_event({
                    "event": "draw",
                    "layer_index": self.current_layer_index,
                    "lines": self.current_layer.lines.copy()
                })
                self.start_drawing_line_index = len(self.current_layer.lines)
                start = event.pos() - QPoint(self.pos_x, self.pos_y)
                end = event.pos() - QPoint(self.pos_x, self.pos_y)
                pen = self.pen(event)
                opacity = 255
                if event.button() == Qt.MouseButton.LeftButton:
                    opacity = self.primary_brush_opacity
                elif event.button() == Qt.MouseButton.RightButton:
                    opacity = self.secondary_brush_opacity
                line = LineData(start, end, pen, self.current_layer_index, opacity)
                start += self.layers[self.current_layer_index].offset
                end += self.layers[self.current_layer_index].offset
                self.current_layer.lines += [line]
            self.handle_tool(event)
            self.update()
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Start dragging the canvas when the middle or right mouse button is pressed
            self.drag_pos = event.pos()

    def mouse_move_event(self, event):
        # check if LeftButton is pressed
        if Qt.MouseButton.LeftButton in event.buttons() or Qt.MouseButton.RightButton in event.buttons():
            self.handle_tool(event)
            self.update()
        elif self.drag_pos is not None:
            self.handle_move_canvas(event)

    def mouse_release_event(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if self.brush_selected:
                self.stop_drawing_line_index = len(self.current_layer.lines)
                self.update()
            elif self.eraser_selected:
                self.is_erasing = False
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Start dragging the canvas when the middle or right mouse button is pressed
            self.drag_pos = event.pos()

    def handle_select(self, event):
        if self.select_selected:
            if self.select_start is None:
                self.select_start = event.pos()
            else:
                self.select_end = event.pos()

        # snap to grid if enabled
        if self.settings_manager.settings.snap_to_grid.get():
            grid_size = self.settings_manager.settings.size.get()
            self.select_start.setX(self.select_start.x() - (self.select_start.x() % grid_size))
            self.select_start.setY(self.select_start.y() - (self.select_start.y() % grid_size))
            self.select_end.setX(self.select_end.x() - (self.select_end.x() % grid_size))
            self.select_end.setY(self.select_end.y() - (self.select_end.y() % grid_size))

        self.update()

    def handle_tool(self, event):
        if self.eraser_selected:
            if not self.is_erasing:
                self.parent.history.add_event({
                    "event": "erase",
                    "layer_index": self.current_layer_index,
                    "lines": self.current_layer.lines.copy(),
                    "images": self.get_image_copy(self.current_layer_index)
                })
            self.handle_erase(event)
            self.parent.is_dirty = True
        elif self.brush_selected:
            self.handle_draw(event)
            self.parent.is_dirty = True
        elif self.move_selected:
            self.handle_move_layer(event)
            self.parent.is_dirty = True
        elif self.select_selected:
            self.handle_select(event)
        elif self.active_grid_area_selected:
            self.handle_move_active_grid_area(event)

    def handle_move_active_grid_area(self, event):
        pos = event.pos()
        point = QPoint(
            pos.x(),
            pos.y()
        )

        # drag from the center of active_grid_area_pivot_point based on the size
        width = self.settings_manager.settings.working_width.get()
        height = self.settings_manager.settings.working_height.get()
        point -= QPoint(
            int((width / 2) + self.pos_x),
            int((height / 2) + self.pos_y)
        )

        if self.settings_manager.settings.snap_to_grid.get():
            point = QPoint(
                point.x() - (point.x() % self.grid_size),
                point.y() - (point.y() % self.grid_size)
            )

        self.active_grid_area_pivot_point = point

        # trigger draw event
        self.update()
