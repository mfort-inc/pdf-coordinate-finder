import os
from pathlib import Path
from typing import Any
import argparse
from dataclasses import dataclass, field
import json

import cv2
import fitz


class PDFDisplay:
    def __init__(self, pdf_path: str):
        self._pdf = fitz.open(pdf_path)
        self._name = Path(pdf_path).name
        self._page = 0
        self._length = len(self._pdf)
        self._img_paths: list[str] = []
        self._img_height = 0  # 이미지 높이를 저장할 변수 추가
        self._display()

    def _display(self) -> None:
        img_path = f"pdfcf_page_{self._page}.png"
        if img_path not in self._img_paths:
            pix = self._pdf[self._page].get_pixmap()
            pix.save(img_path)
            self._img_paths.append(img_path)

        image = cv2.imread(img_path, 1)
        if image is not None:
            self._img_height = image.shape[0]  # 이미지 높이 저장
            cv2.imshow(self.window_name, image)
        else:
            print(f"Failed to load image: {img_path}")

    def move_pages(self, amount: int) -> None:
        self._page = (self._page + amount) % self._length
        self._display()

    def teardown(self) -> None:
        cv2.destroyAllWindows()
        for path in self._img_paths:
            if os.path.exists(path):
                os.remove(path)

    @property
    def window_name(self) -> str:
        return self._name

    @property
    def page(self) -> int:
        return self._page + 1


def prettify_coords(
        obj: dict[int, dict[str, tuple[int, int]]] | dict[int, list[tuple[int, int]]]
) -> str:
    ind = " " * 4
    lines = ["{"]
    for k, v in obj.items():
        if isinstance(v, dict):
            lines.append(f"{ind}{k}: {{")
            for label, coord in v.items():
                lines.append(f'{ind * 2}"{label}": {coord},')
            lines.append(f"{ind}}},")
        else:
            lines.append(f"{ind}{k}: [")
            for coord in v:
                lines.append(f"{ind * 2}{coord},")
            lines.append(f"{ind}],")
    lines.append("}")
    return "\n".join(lines)


@dataclass
class Coordinates:
    get_label: bool
    coords: dict[int, dict[str, tuple[int, int]]] = field(default_factory=dict)
    prev: tuple[int, int] = (0, 0)
    _count: int = 0

    def append(self, x: int, y: int, page: int) -> None:
        label = input("Enter label: ") if self.get_label else str(self._count)
        self.coords.setdefault(page, {})[label] = self.prev = (x, y)
        self._count += 1
        print(f"Stored: page {page}, ({x}, {y})")

    def output(self, output_path: str | None, json_format: bool, pretty_print: bool) -> None:
        # Only display labels if needed
        obj = self.coords if self.get_label else {k : list(v.values()) for k, v in self.coords.items()}

        if pretty_print:
            output: str = json.dumps(obj, indent=4) if json_format else prettify_coords(obj)
        else:
            output = json.dumps(obj) if json_format else str(obj)

        if output_path is not None:
            with open(output_path, "w") as file:
                file.write(output)
            print(f"Results written to '{output_path}'")
        else:
            print(f"\nResults:\n\n{output}\n")


def collect_coordinates(pdf_path: str, adjustment: int, get_label: bool) -> Coordinates:
    print(f"\nOpened '{pdf_path}'")
    if get_label:
        print("You will be prompted to label each coordinate")
    print(
        "\tLEFT CLICK: collect coordinate\n",
        "\tX:          collect, but keep previous x value\n",
        "\tY:          collect, but keep previous y value\n",
        "\t>:          next pdf page\n"
        "\t<:          previous pdf page\n",
        "\tESC:        close the file and print coordinates",
    )

    display = PDFDisplay(pdf_path)
    coords = Coordinates(get_label)
    _x = 0
    _y = 0

    def mouse_callback(event: int, x: int, y: int, flags: int, params: Any | None) -> None:
        nonlocal _x, _y
        if event == cv2.EVENT_LBUTTONDOWN:
            # Y 좌표 반전
            y_new = display._img_height - y + adjustment
            coords.append(x + adjustment, y_new, display.page)
        elif event == cv2.EVENT_MOUSEMOVE:
            _x = x
            _y = y

    cv2.setMouseCallback(display.window_name, mouse_callback)

    while True:
        key = cv2.waitKey(1)
        if key == 27:  # ESC
            break
        elif key in (ord('x'), ord('X')):
            prev_x = coords.prev[0] if coords.coords else _x + adjustment
            y_new = display._img_height - _y + adjustment
            coords.append(prev_x, y_new, display.page)
        elif key in (ord('y'), ord('Y')):
            prev_y = coords.prev[1] if coords.coords else _y + adjustment
            coords.append(_x + adjustment, prev_y, display.page)
        elif key in (ord('<'), ord(',')):
            display.move_pages(-1)
        elif key in (ord('>'), ord('.')):
            display.move_pages(1)
        else:
            if cv2.getWindowProperty(display.window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

    display.teardown()
    return coords


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("-l", "--label_coordinates", action="store_true", help="label each coordinate")
    parser.add_argument("-a", "--adjustment", type=int, default=0, metavar="adjustment", help="value to increase/decrease each coordinate by")
    parser.add_argument("-o", "--output", type=str, metavar="path", help="write results to the specified file")
    parser.add_argument("-j", "--json", action="store_true", help="format results as json instead of python")
    parser.add_argument("-n", "--no_pretty_print", action="store_false", help="output results on one line")
    args = parser.parse_args()

    coordinates = collect_coordinates(args.pdf_path, args.adjustment, args.label_coordinates)
    coordinates.output(args.output, args.json, args.no_pretty_print)
