#!/usr/bin/env python3
"""
3D Model Checker GUI (Enhanced Version)
- 3D 미리보기 패널 통합
- 드래그 앤 드롭 계층 변경
- Undo/Redo 기능
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os
from typing import Optional, List, Dict, Any
import copy

# 3D Visualization
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    print("Warning: CadQuery not available. 3D preview will be limited.")

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("Warning: Plotly not available. HTML 3D viewer will not work.")

# Template system
try:
    from templates import TemplateManager
    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False
    print("Warning: Templates module not available.")

# jupyter_cadquery for native HTML export
try:
    import jupyter_cadquery as jcq
    from cadquery import Assembly, Location, Vector
    JUPYTER_CADQUERY_AVAILABLE = True
except ImportError:
    JUPYTER_CADQUERY_AVAILABLE = False
    print("Warning: jupyter_cadquery not available. Native CadQuery viewer will not work.")


# ============================================================
# Command Pattern for Undo/Redo
# ============================================================

class Command:
    """명령 베이스 클래스"""
    def execute(self) -> bool:
        """명령 실행"""
        raise NotImplementedError

    def undo(self) -> bool:
        """명령 취소"""
        raise NotImplementedError

    def get_description(self) -> str:
        """명령 설명"""
        return "Command"


class AddComponentCommand(Command):
    """컴포넌트 추가 명령"""
    def __init__(self, gui, node_data: Dict[str, Any]):
        self.gui = gui
        self.node_data = copy.deepcopy(node_data)
        self.name = node_data['name']

    def execute(self) -> bool:
        return self.gui._add_component_impl(self.node_data)

    def undo(self) -> bool:
        return self.gui._delete_component_impl(self.name)

    def get_description(self) -> str:
        return f"Add '{self.name}'"


class DeleteComponentCommand(Command):
    """컴포넌트 삭제 명령"""
    def __init__(self, gui, name: str):
        self.gui = gui
        self.name = name
        # 삭제 전 데이터 백업 (자식 포함)
        self.backup_data = self.gui._backup_subtree(name)

    def execute(self) -> bool:
        return self.gui._delete_component_impl(self.name)

    def undo(self) -> bool:
        return self.gui._restore_subtree(self.backup_data)

    def get_description(self) -> str:
        return f"Delete '{self.name}'"


class UpdateComponentCommand(Command):
    """컴포넌트 수정 명령"""
    def __init__(self, gui, name: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        self.gui = gui
        self.name = name
        self.old_data = copy.deepcopy(old_data)
        self.new_data = copy.deepcopy(new_data)

    def execute(self) -> bool:
        return self.gui._update_component_impl(self.name, self.new_data)

    def undo(self) -> bool:
        return self.gui._update_component_impl(self.name, self.old_data)

    def get_description(self) -> str:
        return f"Update '{self.name}'"


class MoveComponentCommand(Command):
    """컴포넌트 이동 명령 (부모 변경)"""
    def __init__(self, gui, name: str, old_parent: str, new_parent: str):
        self.gui = gui
        self.name = name
        self.old_parent = old_parent
        self.new_parent = new_parent

    def execute(self) -> bool:
        return self.gui._move_component_impl(self.name, self.new_parent)

    def undo(self) -> bool:
        return self.gui._move_component_impl(self.name, self.old_parent)

    def get_description(self) -> str:
        return f"Move '{self.name}' to '{self.new_parent}'"


class CommandHistory:
    """명령 히스토리 관리"""
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def execute(self, command: Command) -> bool:
        """명령 실행 및 히스토리에 추가"""
        if command.execute():
            self.undo_stack.append(command)
            if len(self.undo_stack) > self.max_size:
                self.undo_stack.pop(0)
            self.redo_stack.clear()  # 새 명령 실행 시 redo 스택 초기화
            return True
        return False

    def undo(self) -> bool:
        """마지막 명령 취소"""
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        if command.undo():
            self.redo_stack.append(command)
            return True
        else:
            self.undo_stack.append(command)  # 실패 시 다시 추가
            return False

    def redo(self) -> bool:
        """취소한 명령 재실행"""
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        if command.execute():
            self.undo_stack.append(command)
            return True
        else:
            self.redo_stack.append(command)  # 실패 시 다시 추가
            return False

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def clear(self):
        """히스토리 초기화"""
        self.undo_stack.clear()
        self.redo_stack.clear()


# ============================================================
# Component Node
# ============================================================

class ComponentNode:
    """컴포넌트 트리 노드"""
    def __init__(self, name, node_type='assembly', parent=None):
        self.name = name
        self.type = node_type  # assembly, box, cyl, sphere
        self.parent = parent
        self.children = []

        # 형상 파라미터
        self.L = 0.0
        self.W = 0.0
        self.T = 0.0
        self.D = 0.0
        self.H = 0.0

        # 위치 파라미터
        self.cx = 0.0
        self.cy = 0.0
        self.cz = 0.0

        # 기타
        self.color = ''
        self.coord_file = ''
        self.coord_has_header = True

    def add_child(self, child):
        """자식 노드 추가"""
        if child not in self.children:
            self.children.append(child)
        child.parent = self

    def remove_child(self, child):
        """자식 노드 제거"""
        if child in self.children:
            self.children.remove(child)
        child.parent = None

    def to_dict(self):
        """CSV 저장을 위한 딕셔너리 변환"""
        parent_name = self.parent.name if self.parent else 'root'
        return {
            'name': self.name,
            'type': self.type,
            'parent': parent_name,
            'L': self.L if self.type == 'box' else '',
            'W': self.W if self.type == 'box' else '',
            'T': self.T if self.type == 'box' else '',
            'D': self.D if self.type in ['cyl', 'sphere'] else '',
            'H': self.H if self.type == 'cyl' else '',
            'cx': self.cx if self.type != 'assembly' else '',
            'cy': self.cy if self.type != 'assembly' else '',
            'cz': self.cz if self.type != 'assembly' else '',
            'color': self.color,
            'coord_file': self.coord_file,
            'coord_has_header': 'true' if self.coord_has_header else 'false'
        }

    def get_data_dict(self):
        """내부 데이터를 딕셔너리로 (Undo/Redo용)"""
        return {
            'name': self.name,
            'type': self.type,
            'parent': self.parent.name if self.parent else 'root',
            'L': self.L,
            'W': self.W,
            'T': self.T,
            'D': self.D,
            'H': self.H,
            'cx': self.cx,
            'cy': self.cy,
            'cz': self.cz,
            'color': self.color,
            'coord_file': self.coord_file,
            'coord_has_header': self.coord_has_header
        }

    def set_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 데이터 설정"""
        self.type = data.get('type', self.type)
        self.L = data.get('L', 0.0)
        self.W = data.get('W', 0.0)
        self.T = data.get('T', 0.0)
        self.D = data.get('D', 0.0)
        self.H = data.get('H', 0.0)
        self.cx = data.get('cx', 0.0)
        self.cy = data.get('cy', 0.0)
        self.cz = data.get('cz', 0.0)
        self.color = data.get('color', '')
        self.coord_file = data.get('coord_file', '')
        self.coord_has_header = data.get('coord_has_header', True)


# ============================================================
# 3D Viewer Panel
# ============================================================

class Viewer3DPanel:
    """3D 미리보기 패널"""
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="3D 미리보기", padding=5)

        # Matplotlib Figure (크기 고정)
        self.fig = Figure(figsize=(7, 7), dpi=80)
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)  # 여백 고정
        self.ax = self.fig.add_subplot(111, projection='3d')

        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.draw()
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, self.frame)
        toolbar.update()

        # 초기 설정
        self.setup_axes()

    def setup_axes(self):
        """축 설정"""
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_title('3D Preview')

    def clear(self):
        """화면 초기화"""
        self.ax.clear()
        self.setup_axes()
        self.canvas.draw()

    def render_components(self, components: Dict[str, ComponentNode]):
        """컴포넌트들을 3D로 렌더링"""
        self.ax.clear()
        self.setup_axes()

        if not CADQUERY_AVAILABLE:
            self.ax.text(0, 0, 0, 'CadQuery not available', fontsize=12)
            self.canvas.draw()
            return

        # 모든 형상 수집
        shapes = []
        colors = []

        for name, node in components.items():
            if node.type == 'assembly' or name == 'root':
                continue

            try:
                # 형상 생성
                shape = self._create_shape(node)
                if shape is not None:
                    shapes.append(shape)
                    colors.append(node.color if node.color else 'lightblue')
            except Exception as e:
                print(f"Error creating shape for {name}: {e}")
                continue

        # 렌더링
        if shapes:
            self._render_shapes(shapes, colors)

        self.canvas.draw()

    def _create_shape(self, node: ComponentNode):
        """노드에서 CadQuery 형상 생성"""
        if node.type == 'box':
            if node.L <= 0 or node.W <= 0 or node.T <= 0:
                return None
            shape = cq.Workplane("XY").box(node.L, node.W, node.T).val()
            # 위치 이동
            center_z = node.cz + node.T / 2
            shape = shape.translate((node.cx, node.cy, center_z))
            return shape

        elif node.type == 'cyl':
            if node.D <= 0 or node.H <= 0:
                return None
            shape = cq.Workplane("XY").circle(node.D/2).extrude(node.H).val()
            # 위치 이동
            center_z = node.cz + node.H / 2
            shape = shape.translate((node.cx, node.cy, center_z - node.H/2))
            return shape

        elif node.type == 'sphere':
            if node.D <= 0:
                return None
            shape = cq.Workplane("XY").sphere(node.D/2).val()
            # 위치 이동
            center_z = node.cz + node.D / 2
            shape = shape.translate((node.cx, node.cy, center_z))
            return shape

        return None

    def _render_shapes(self, shapes, colors):
        """CadQuery 형상들을 matplotlib로 렌더링"""
        all_vertices = []

        for shape, color in zip(shapes, colors):
            try:
                # Tessellate
                vertices, triangles = self._tessellate_shape(shape)

                if len(vertices) > 0 and len(triangles) > 0:
                    # 삼각형 메시 생성
                    poly = Poly3DCollection(triangles, alpha=0.7, linewidths=0.5, edgecolors='black')
                    poly.set_facecolor(color)
                    self.ax.add_collection3d(poly)

                    all_vertices.extend(vertices)
                else:
                    print(f"Warning: Shape has no vertices or triangles (v={len(vertices)}, t={len(triangles)})")

            except Exception as e:
                print(f"Error rendering shape: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 축 범위 설정
        if all_vertices:
            try:
                all_vertices = np.array(all_vertices)
                max_range = np.array([
                    all_vertices[:, 0].max() - all_vertices[:, 0].min(),
                    all_vertices[:, 1].max() - all_vertices[:, 1].min(),
                    all_vertices[:, 2].max() - all_vertices[:, 2].min()
                ]).max() / 2.0

                mid_x = (all_vertices[:, 0].max() + all_vertices[:, 0].min()) * 0.5
                mid_y = (all_vertices[:, 1].max() + all_vertices[:, 1].min()) * 0.5
                mid_z = (all_vertices[:, 2].max() + all_vertices[:, 2].min()) * 0.5

                self.ax.set_xlim(mid_x - max_range, mid_x + max_range)
                self.ax.set_ylim(mid_y - max_range, mid_y + max_range)
                self.ax.set_zlim(mid_z - max_range, mid_z + max_range)
            except Exception as e:
                print(f"Error setting axis limits: {e}")
                # 기본 범위 설정
                self.ax.set_xlim(-50, 50)
                self.ax.set_ylim(-50, 50)
                self.ax.set_zlim(-50, 50)

    def _tessellate_shape(self, shape):
        """CadQuery 형상을 삼각형 메시로 변환"""
        # Tessellate using CadQuery
        all_vertices = []
        all_triangles = []

        try:
            # Get faces
            faces = shape.Faces()

            for face in faces:
                # Get vertices and triangles from face
                face_data = face.tessellate(0.1)  # tolerance

                if len(face_data) == 2:
                    verts, tris = face_data

                    # Vector 객체를 (x, y, z) 튜플로 변환
                    # CadQuery의 Vector 객체는 .toTuple() 메서드를 가지고 있음
                    verts_list = [v.toTuple() if hasattr(v, 'toTuple') else (v.x, v.y, v.z) for v in verts]

                    # vertices를 numpy 배열로 변환 (튜플 리스트 -> (N, 3) 배열)
                    verts_array = np.array(verts_list, dtype=np.float64)

                    # 전체 vertices에 추가 (튜플 형태로)
                    all_vertices.extend(verts_list)

                    # 삼각형 생성 (각 삼각형은 (3, 3) numpy 배열)
                    for tri in tris:
                        # tri는 [idx0, idx1, idx2] 형태의 인덱스 배열
                        # verts_array[tri]로 직접 인덱싱하면 (3, 3) 배열 생성
                        triangle = verts_array[list(tri)]
                        all_triangles.append(triangle)

        except Exception as e:
            print(f"Tessellation error: {e}")
            import traceback
            traceback.print_exc()

        return all_vertices, all_triangles


# ============================================================
# Main GUI
# ============================================================

class ModelCheckerGUI:
    """3D Model Checker GUI 메인 클래스 (Enhanced)"""

    def __init__(self, root):
        self.root = root
        self.root.title("3D Model Checker GUI - Enhanced")
        self.root.geometry("1600x900")

        # 창 최소 크기 설정 (레이아웃 고정)
        self.root.minsize(1400, 800)

        # 스크립트 실행 위치 저장 (모든 파일이 여기에 저장됨)
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # 루트 노드
        self.root_node = ComponentNode('root', 'assembly')
        self.components = {'root': self.root_node}

        # Command History
        self.history = CommandHistory()

        # 드래그 앤 드롭 상태
        self.drag_item = None

        self.setup_ui()
        self.setup_keyboard_shortcuts()

    def setup_keyboard_shortcuts(self):
        """키보드 단축키 설정"""
        self.root.bind('<Control-z>', lambda e: self.undo())
        self.root.bind('<Control-y>', lambda e: self.redo())
        self.root.bind('<Control-s>', lambda e: self.save_csv())
        self.root.bind('<Control-o>', lambda e: self.load_csv())
        self.root.bind('<F5>', lambda e: self.refresh_3d_view())

    def setup_ui(self):
        """UI 구성 (3분할 레이아웃)"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 좌측: 트리 뷰 (30%)
        left_frame = ttk.LabelFrame(main_frame, text="Assembly 구조", padding=5)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 3))

        # 중앙: 3D 뷰어 (40%)
        self.viewer_3d = Viewer3DPanel(main_frame)
        self.viewer_3d.frame.grid(row=0, column=1, sticky='nsew', padx=3)

        # 우측: 입력 폼 (30%)
        right_frame = ttk.LabelFrame(main_frame, text="컴포넌트 편집", padding=5)
        right_frame.grid(row=0, column=2, sticky='nsew', padx=(3, 0))

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=4)
        main_frame.columnconfigure(2, weight=3)
        main_frame.rowconfigure(0, weight=1)

        # === 좌측 트리 뷰 ===
        self.setup_tree_view(left_frame)

        # === 우측 입력 폼 ===
        self.setup_input_form(right_frame)

        # === 하단 버튼 ===
        self.setup_bottom_buttons()

    def setup_tree_view(self, parent):
        """트리 뷰 설정"""
        # 버튼 프레임
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(btn_frame, text="↶ Undo", command=self.undo, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="↷ Redo", command=self.redo, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑 삭제", command=self.delete_component, width=8).pack(side=tk.RIGHT, padx=2)

        # 스크롤바
        tree_scroll = ttk.Scrollbar(parent)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 트리 뷰
        self.tree = ttk.Treeview(parent, yscrollcommand=tree_scroll.set, selectmode='browse')
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        # 컬럼 설정
        self.tree['columns'] = ('type', 'dimensions')
        self.tree.column('#0', width=180, minwidth=120)
        self.tree.column('type', width=70, minwidth=50)
        self.tree.column('dimensions', width=120, minwidth=80)

        self.tree.heading('#0', text='이름')
        self.tree.heading('type', text='타입')
        self.tree.heading('dimensions', text='치수')

        # ROOT 추가
        self.tree.insert('', 'end', 'root', text='ROOT', values=('assembly', ''), open=True)

        # 이벤트 바인딩
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<B1-Motion>', self.on_tree_drag)
        self.tree.bind('<ButtonRelease-1>', self.on_tree_drop)

    def setup_input_form(self, parent):
        """입력 폼 설정"""
        # 스크롤 가능한 캔버스
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        form = scrollable_frame
        row = 0

        # 이름
        ttk.Label(form, text="이름:").grid(row=row, column=0, sticky='w', pady=2, padx=(5, 2))
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=25).grid(row=row, column=1, sticky='ew', pady=2, padx=(2, 5))
        row += 1

        # 타입
        ttk.Label(form, text="타입:").grid(row=row, column=0, sticky='w', pady=2, padx=(5, 2))
        self.type_var = tk.StringVar(value='box')
        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky='w', pady=2, padx=(2, 5))
        ttk.Radiobutton(type_frame, text='Asm', variable=self.type_var,
                       value='assembly', command=self.on_type_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(type_frame, text='Box', variable=self.type_var,
                       value='box', command=self.on_type_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(type_frame, text='Cyl', variable=self.type_var,
                       value='cyl', command=self.on_type_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(type_frame, text='Sph', variable=self.type_var,
                       value='sphere', command=self.on_type_change).pack(side=tk.LEFT, padx=2)
        row += 1

        # 부모 선택
        ttk.Label(form, text="부모:").grid(row=row, column=0, sticky='w', pady=2, padx=(5, 2))
        self.parent_var = tk.StringVar(value='root')
        self.parent_combo = ttk.Combobox(form, textvariable=self.parent_var, width=23)
        self.parent_combo.grid(row=row, column=1, sticky='ew', pady=2, padx=(2, 5))
        self.update_parent_combo()
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 형상 파라미터 ===
        ttk.Label(form, text="형상 파라미터", font=('', 9, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=2, padx=(5, 2))
        row += 1

        # 형상 파라미터 컨테이너 (고정 높이로 위치 고정)
        self.shape_params_container = ttk.Frame(form, height=120)
        self.shape_params_container.grid(row=row, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
        self.shape_params_container.grid_propagate(False)  # 고정 높이 유지

        # Box
        self.box_frame = ttk.LabelFrame(self.shape_params_container, text="Box", padding=5)
        self.L_var = tk.DoubleVar(value=0.0)
        self.W_var = tk.DoubleVar(value=0.0)
        self.T_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.box_frame, text="L:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.L_var, width=12).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.box_frame, text="W:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.W_var, width=12).grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Label(self.box_frame, text="T:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.T_var, width=12).grid(row=2, column=1, sticky='ew', pady=2)

        # Cylinder
        self.cyl_frame = ttk.LabelFrame(self.shape_params_container, text="Cylinder", padding=5)
        self.D_cyl_var = tk.DoubleVar(value=0.0)
        self.H_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.cyl_frame, text="D:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.cyl_frame, textvariable=self.D_cyl_var, width=12).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.cyl_frame, text="H:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.cyl_frame, textvariable=self.H_var, width=12).grid(row=1, column=1, sticky='ew', pady=2)
        # Sphere용 빈 공간 추가 (높이 맞추기)
        ttk.Label(self.cyl_frame, text="").grid(row=2, column=0, sticky='w', pady=2)

        # Sphere
        self.sphere_frame = ttk.LabelFrame(self.shape_params_container, text="Sphere", padding=5)
        self.D_sphere_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.sphere_frame, text="D:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.sphere_frame, textvariable=self.D_sphere_var, width=12).grid(row=0, column=1, sticky='ew', pady=2)
        # Box와 높이 맞추기 위한 빈 공간
        ttk.Label(self.sphere_frame, text="").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Label(self.sphere_frame, text="").grid(row=2, column=0, sticky='w', pady=2)

        # 초기에는 box_frame만 표시
        self.box_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 위치 파라미터 ===
        ttk.Label(form, text="위치", font=('', 9, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=2, padx=(5, 2))
        row += 1

        self.position_frame = ttk.Frame(form)
        self.cx_var = tk.DoubleVar(value=0.0)
        self.cy_var = tk.DoubleVar(value=0.0)
        self.cz_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.position_frame, text="cx:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cx_var, width=12).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.position_frame, text="cy:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cy_var, width=12).grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Label(self.position_frame, text="cz:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cz_var, width=12).grid(row=2, column=1, sticky='ew', pady=2)

        self.position_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 기타 ===
        ttk.Label(form, text="색상:").grid(row=row, column=0, sticky='w', pady=2, padx=(5, 2))
        self.color_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.color_var, width=25).grid(row=row, column=1, sticky='ew', pady=2, padx=(2, 5))
        row += 1

        ttk.Label(form, text="좌표 파일:").grid(row=row, column=0, sticky='w', pady=2, padx=(5, 2))
        coord_frame = ttk.Frame(form)
        coord_frame.grid(row=row, column=1, sticky='ew', pady=2, padx=(2, 5))
        self.coord_file_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.coord_file_var, width=15).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(coord_frame, text="...", command=self.browse_coord_file, width=3).pack(side=tk.LEFT, padx=(2, 0))
        row += 1

        self.coord_header_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="헤더 있음", variable=self.coord_header_var).grid(row=row, column=1, sticky='w', pady=2, padx=(2, 5))
        row += 1

        # 버튼
        button_frame = ttk.Frame(form)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="추가", command=self.add_component, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="수정", command=self.update_component, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="초기화", command=self.clear_form, width=10).pack(side=tk.LEFT, padx=3)
        row += 1

        # 실시간 미리보기 버튼
        ttk.Button(form, text="🔄 3D 새로고침 (F5)", command=self.refresh_3d_view).grid(row=row, column=0, columnspan=2, pady=5, sticky='ew', padx=5)
        row += 1

        self.on_type_change()

    def setup_bottom_buttons(self):
        """하단 버튼"""
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_frame, text="📋 템플릿", command=self.open_template_selector).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="💾 CSV 저장 (Ctrl+S)", command=self.save_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="📂 CSV 불러오기 (Ctrl+O)", command=self.load_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🌐 Plotly HTML", command=self.open_html_3d_viewer).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔧 CadQuery HTML", command=self.open_cadquery_html_viewer).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🚀 Jupyter 뷰어", command=self.run_3d_viewer).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="종료", command=self.root.quit).pack(side=tk.RIGHT, padx=2)

    # ============================================================
    # Drag & Drop
    # ============================================================

    def on_tree_click(self, event):
        """트리 클릭 시작"""
        item = self.tree.identify('item', event.x, event.y)
        if item:
            self.drag_item = item

    def on_tree_drag(self, event):
        """드래그 중"""
        if self.drag_item:
            # 드래그 피드백 (선택 상태 유지)
            self.tree.selection_set(self.drag_item)

    def on_tree_drop(self, event):
        """드롭"""
        if not self.drag_item:
            return

        drop_target = self.tree.identify('item', event.x, event.y)

        if drop_target and drop_target != self.drag_item:
            # 드롭 대상이 assembly인지 확인
            if drop_target in self.components:
                target_node = self.components[drop_target]

                if target_node.type == 'assembly' or drop_target == 'root':
                    # 이동 가능한지 확인 (자기 자신의 자손에게는 이동 불가)
                    if not self._is_descendant(drop_target, self.drag_item):
                        # 이동 명령 실행
                        source_node = self.components[self.drag_item]
                        old_parent = source_node.parent.name if source_node.parent else 'root'

                        if old_parent != drop_target:
                            cmd = MoveComponentCommand(self, self.drag_item, old_parent, drop_target)
                            if self.history.execute(cmd):
                                messagebox.showinfo("성공", f"'{self.drag_item}'를 '{drop_target}'로 이동")
                                self.refresh_3d_view()
                    else:
                        messagebox.showerror("오류", "자기 자신의 자손으로는 이동할 수 없습니다.")
                else:
                    messagebox.showerror("오류", "Assembly에만 드롭할 수 있습니다.")

        self.drag_item = None

    def _is_descendant(self, ancestor: str, descendant: str) -> bool:
        """ancestor가 descendant의 조상인지 확인"""
        if ancestor not in self.components or descendant not in self.components:
            return False

        node = self.components[descendant]
        while node.parent:
            if node.parent.name == ancestor:
                return True
            node = node.parent

        return False

    # ============================================================
    # Command Implementations
    # ============================================================

    def _add_component_impl(self, node_data: Dict[str, Any]) -> bool:
        """컴포넌트 추가 구현"""
        name = node_data['name']
        parent_name = node_data['parent']

        if name in self.components:
            return False

        if parent_name not in self.components:
            return False

        node = ComponentNode(name, node_data['type'], self.components[parent_name])
        node.set_from_dict(node_data)

        self.components[name] = node
        self.components[parent_name].add_child(node)

        # 트리뷰 업데이트
        dimensions = self.get_dimension_str(node)
        self.tree.insert(parent_name, 'end', name, text=name, values=(node.type, dimensions))

        self.update_parent_combo()
        return True

    def _delete_component_impl(self, name: str) -> bool:
        """컴포넌트 삭제 구현"""
        if name == 'root' or name not in self.components:
            return False

        # 재귀적으로 삭제
        self._delete_recursive(name)

        # 트리뷰 업데이트
        if self.tree.exists(name):
            self.tree.delete(name)

        self.update_parent_combo()
        return True

    def _delete_recursive(self, name: str):
        """재귀적으로 노드 삭제"""
        if name not in self.components:
            return

        node = self.components[name]
        for child in list(node.children):
            self._delete_recursive(child.name)

        if node.parent:
            node.parent.remove_child(node)

        del self.components[name]

    def _update_component_impl(self, name: str, new_data: Dict[str, Any]) -> bool:
        """컴포넌트 수정 구현"""
        if name not in self.components:
            return False

        node = self.components[name]
        node.set_from_dict(new_data)

        # 트리뷰 업데이트
        dimensions = self.get_dimension_str(node)
        self.tree.item(name, values=(node.type, dimensions))

        return True

    def _move_component_impl(self, name: str, new_parent_name: str) -> bool:
        """컴포넌트 이동 구현"""
        if name not in self.components or new_parent_name not in self.components:
            return False

        node = self.components[name]
        new_parent = self.components[new_parent_name]
        old_parent = node.parent

        if new_parent.type != 'assembly' and new_parent_name != 'root':
            return False

        # 이동
        if old_parent:
            old_parent.remove_child(node)

        new_parent.add_child(node)

        # 트리뷰 업데이트
        self.tree.move(name, new_parent_name, 'end')

        return True

    def _backup_subtree(self, name: str) -> List[Dict[str, Any]]:
        """서브트리 백업 (Undo용)"""
        if name not in self.components:
            return []

        backup = []
        node = self.components[name]

        # 현재 노드 백업
        backup.append(node.get_data_dict())

        # 자식들 재귀적으로 백업
        for child in node.children:
            backup.extend(self._backup_subtree(child.name))

        return backup

    def _restore_subtree(self, backup_data: List[Dict[str, Any]]) -> bool:
        """서브트리 복원 (Undo용)"""
        if not backup_data:
            return False

        # 순서대로 복원
        for data in backup_data:
            if data['name'] not in self.components:
                self._add_component_impl(data)

        return True

    # ============================================================
    # Undo/Redo
    # ============================================================

    def undo(self):
        """Undo"""
        if self.history.undo():
            messagebox.showinfo("Undo", "마지막 작업 취소됨")
            self.refresh_3d_view()
        else:
            messagebox.showwarning("Undo", "취소할 작업이 없습니다.")

    def redo(self):
        """Redo"""
        if self.history.redo():
            messagebox.showinfo("Redo", "작업 재실행됨")
            self.refresh_3d_view()
        else:
            messagebox.showwarning("Redo", "재실행할 작업이 없습니다.")

    # ============================================================
    # UI Callbacks
    # ============================================================

    def on_type_change(self):
        """타입 변경 시 (고정 위치 유지)"""
        node_type = self.type_var.get()

        # 형상 파라미터 프레임 숨기기 (place 사용)
        self.box_frame.place_forget()
        self.cyl_frame.place_forget()
        self.sphere_frame.place_forget()

        # 위치 파라미터는 grid 사용
        self.position_frame.grid_remove()

        # 타입에 따라 적절한 프레임 표시
        if node_type == 'box':
            self.box_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.position_frame.grid()
        elif node_type == 'cyl':
            self.cyl_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.position_frame.grid()
        elif node_type == 'sphere':
            self.sphere_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.position_frame.grid()
        # assembly는 형상/위치 파라미터 모두 숨김

    def browse_coord_file(self):
        """좌표 파일 찾기"""
        filename = filedialog.askopenfilename(
            title="좌표 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )
        if filename:
            self.coord_file_var.set(filename)

    def update_parent_combo(self):
        """부모 콤보박스 업데이트"""
        assemblies = ['root']
        for name, node in self.components.items():
            if node.type == 'assembly' and name != 'root':
                assemblies.append(name)
        self.parent_combo['values'] = assemblies

    def add_component(self):
        """컴포넌트 추가"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("오류", "이름을 입력하세요.")
            return

        if name in self.components:
            messagebox.showerror("오류", f"'{name}'은(는) 이미 존재합니다.")
            return

        parent_name = self.parent_var.get()

        # 노드 데이터 준비
        node_data = {
            'name': name,
            'type': self.type_var.get(),
            'parent': parent_name,
            'L': self.L_var.get(),
            'W': self.W_var.get(),
            'T': self.T_var.get(),
            'D': self.D_cyl_var.get() if self.type_var.get() == 'cyl' else self.D_sphere_var.get(),
            'H': self.H_var.get(),
            'cx': self.cx_var.get(),
            'cy': self.cy_var.get(),
            'cz': self.cz_var.get(),
            'color': self.color_var.get(),
            'coord_file': self.coord_file_var.get(),
            'coord_has_header': self.coord_header_var.get()
        }

        # 명령 실행
        cmd = AddComponentCommand(self, node_data)
        if self.history.execute(cmd):
            messagebox.showinfo("성공", f"'{name}' 추가됨")
            self.clear_form()
            self.refresh_3d_view()
        else:
            messagebox.showerror("오류", "추가 실패")

    def update_component(self):
        """컴포넌트 수정"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("오류", "수정할 컴포넌트를 선택하세요.")
            return

        item_id = selection[0]
        if item_id == 'root':
            messagebox.showerror("오류", "ROOT는 수정할 수 없습니다.")
            return

        node = self.components[item_id]
        old_data = node.get_data_dict()

        # 새 데이터
        new_data = {
            'name': item_id,
            'type': self.type_var.get(),
            'parent': node.parent.name if node.parent else 'root',
            'L': self.L_var.get(),
            'W': self.W_var.get(),
            'T': self.T_var.get(),
            'D': self.D_cyl_var.get() if self.type_var.get() == 'cyl' else self.D_sphere_var.get(),
            'H': self.H_var.get(),
            'cx': self.cx_var.get(),
            'cy': self.cy_var.get(),
            'cz': self.cz_var.get(),
            'color': self.color_var.get(),
            'coord_file': self.coord_file_var.get(),
            'coord_has_header': self.coord_header_var.get()
        }

        # 명령 실행
        cmd = UpdateComponentCommand(self, item_id, old_data, new_data)
        if self.history.execute(cmd):
            messagebox.showinfo("성공", f"'{item_id}' 수정됨")
            self.refresh_3d_view()
        else:
            messagebox.showerror("오류", "수정 실패")

    def delete_component(self):
        """컴포넌트 삭제"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("오류", "삭제할 컴포넌트를 선택하세요.")
            return

        item_id = selection[0]
        if item_id == 'root':
            messagebox.showerror("오류", "ROOT는 삭제할 수 없습니다.")
            return

        if messagebox.askyesno("확인", f"'{item_id}'를 삭제하시겠습니까?"):
            cmd = DeleteComponentCommand(self, item_id)
            if self.history.execute(cmd):
                messagebox.showinfo("성공", f"'{item_id}' 삭제됨")
                self.clear_form()
                self.refresh_3d_view()
            else:
                messagebox.showerror("오류", "삭제 실패")

    def on_tree_select(self, event):
        """트리 선택 시"""
        selection = self.tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id not in self.components:
            return

        node = self.components[item_id]

        self.name_var.set(node.name)
        self.type_var.set(node.type)
        self.parent_var.set(node.parent.name if node.parent else 'root')

        self.L_var.set(node.L)
        self.W_var.set(node.W)
        self.T_var.set(node.T)
        self.D_cyl_var.set(node.D)
        self.D_sphere_var.set(node.D)
        self.H_var.set(node.H)

        self.cx_var.set(node.cx)
        self.cy_var.set(node.cy)
        self.cz_var.set(node.cz)

        self.color_var.set(node.color)
        self.coord_file_var.set(node.coord_file)
        self.coord_header_var.set(node.coord_has_header)

        self.on_type_change()

    def clear_form(self):
        """폼 초기화"""
        self.name_var.set('')
        self.type_var.set('box')
        self.parent_var.set('root')

        self.L_var.set(0.0)
        self.W_var.set(0.0)
        self.T_var.set(0.0)
        self.D_cyl_var.set(0.0)
        self.D_sphere_var.set(0.0)
        self.H_var.set(0.0)

        self.cx_var.set(0.0)
        self.cy_var.set(0.0)
        self.cz_var.set(0.0)

        self.color_var.set('')
        self.coord_file_var.set('')
        self.coord_header_var.set(True)

        self.on_type_change()

    def get_dimension_str(self, node):
        """치수 문자열"""
        if node.type == 'assembly':
            return ''
        elif node.type == 'box':
            return f"{node.L}×{node.W}×{node.T}"
        elif node.type == 'cyl':
            return f"D{node.D}×H{node.H}"
        elif node.type == 'sphere':
            return f"D{node.D}"
        return ''

    # ============================================================
    # 3D Viewer
    # ============================================================

    def refresh_3d_view(self):
        """3D 뷰 새로고침"""
        try:
            self.viewer_3d.render_components(self.components)
        except Exception as e:
            print(f"3D 렌더링 오류: {e}")
            messagebox.showerror("3D 렌더링 오류", str(e))

    # ============================================================
    # CSV
    # ============================================================

    def save_csv(self):
        """CSV 저장"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
            initialfile="components.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['name', 'type', 'parent', 'L', 'W', 'T', 'D', 'H',
                             'cx', 'cy', 'cz', 'color', 'coord_file', 'coord_has_header']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for name, node in self.components.items():
                    if name == 'root':
                        continue
                    writer.writerow(node.to_dict())

            messagebox.showinfo("성공", f"CSV 파일 저장됨:\n{filename}")
        except Exception as e:
            messagebox.showerror("오류", f"CSV 저장 실패:\n{str(e)}")

    def load_csv(self):
        """CSV 불러오기"""
        filename = filedialog.askopenfilename(
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )

        if not filename:
            return

        try:
            # 초기화
            for name in list(self.components.keys()):
                if name != 'root':
                    del self.components[name]

            self.root_node.children = []

            for item in self.tree.get_children('root'):
                self.tree.delete(item)

            # CSV 읽기
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Assembly 먼저
            for row in rows:
                if row['type'].strip().lower() == 'assembly':
                    name = row['name'].strip()
                    parent_name = row.get('parent', '').strip() or 'root'

                    if parent_name not in self.components:
                        continue

                    node = ComponentNode(name, 'assembly', self.components[parent_name])
                    self.components[name] = node
                    self.components[parent_name].add_child(node)

                    self.tree.insert(parent_name, 'end', name, text=name, values=('assembly', ''))

            # 나머지
            for row in rows:
                node_type = row['type'].strip().lower()
                if node_type == 'assembly':
                    continue

                name = row['name'].strip()
                parent_name = row.get('parent', '').strip() or 'root'

                if parent_name not in self.components:
                    continue

                node = ComponentNode(name, node_type, self.components[parent_name])

                node.L = float(row.get('L', 0) or 0)
                node.W = float(row.get('W', 0) or 0)
                node.T = float(row.get('T', 0) or 0)
                node.D = float(row.get('D', 0) or 0)
                node.H = float(row.get('H', 0) or 0)
                node.cx = float(row.get('cx', 0) or 0)
                node.cy = float(row.get('cy', 0) or 0)
                node.cz = float(row.get('cz', 0) or 0)
                node.color = row.get('color', '').strip()
                node.coord_file = row.get('coord_file', '').strip()
                coord_header = row.get('coord_has_header', '').strip().lower()
                node.coord_has_header = coord_header in ['true', '1', 'yes', 'y']

                self.components[name] = node
                self.components[parent_name].add_child(node)

                dimensions = self.get_dimension_str(node)
                self.tree.insert(parent_name, 'end', name, text=name, values=(node_type, dimensions))

            self.update_parent_combo()
            self.history.clear()  # 히스토리 초기화
            messagebox.showinfo("성공", f"CSV 파일 불러옴:\n{filename}")
            self.refresh_3d_view()

        except Exception as e:
            messagebox.showerror("오류", f"CSV 불러오기 실패:\n{str(e)}")

    def open_template_selector(self):
        """템플릿 선택기 열기"""
        if not TEMPLATES_AVAILABLE:
            messagebox.showerror("오류", "템플릿 모듈을 찾을 수 없습니다.")
            return

        manager = TemplateManager(self.root, self._on_template_generate)
        manager.show_selector()

    def _on_template_generate(self, components: List[Dict[str, Any]]):
        """템플릿에서 생성된 컴포넌트들을 추가"""
        # 기존 컴포넌트 초기화 확인
        if len(self.components) > 1:  # root 외에 다른 것이 있으면
            if not messagebox.askyesno("확인", "현재 컴포넌트를 모두 삭제하고 템플릿을 적용하시겠습니까?"):
                return

            # 기존 컴포넌트 삭제
            for name in list(self.components.keys()):
                if name != 'root':
                    del self.components[name]
            self.root_node.children = []

            for item in self.tree.get_children('root'):
                self.tree.delete(item)

        # 히스토리 초기화
        self.history.clear()

        # 컴포넌트 추가 (assembly 먼저)
        for comp in components:
            if comp['type'] == 'assembly':
                self._add_component_impl(comp)

        # 나머지 컴포넌트 추가
        for comp in components:
            if comp['type'] != 'assembly':
                self._add_component_impl(comp)

        self.update_parent_combo()
        self.refresh_3d_view()

    def open_html_3d_viewer(self):
        """HTML 3D 뷰어 열기 (Plotly 사용, Jupyter 불필요)"""
        if not PLOTLY_AVAILABLE:
            messagebox.showerror("오류", "Plotly가 설치되지 않았습니다.\npip install plotly")
            return

        if not CADQUERY_AVAILABLE:
            messagebox.showerror("오류", "CadQuery가 설치되지 않았습니다.")
            return

        try:
            # Plotly Figure 생성
            fig = go.Figure()

            # 각 컴포넌트를 3D 메시로 추가
            for name, node in self.components.items():
                if node.type == 'assembly' or name == 'root':
                    continue

                # 형상 생성
                shape = self._create_shape_for_plotly(node)
                if shape is None:
                    continue

                # Tessellate
                vertices, triangles = self._tessellate_for_plotly(shape)

                if len(vertices) > 0 and len(triangles) > 0:
                    vertices = np.array(vertices)
                    triangles = np.array(triangles)

                    # Plotly Mesh3d 추가
                    fig.add_trace(go.Mesh3d(
                        x=vertices[:, 0],
                        y=vertices[:, 1],
                        z=vertices[:, 2],
                        i=triangles[:, 0],
                        j=triangles[:, 1],
                        k=triangles[:, 2],
                        name=name,
                        color=node.color if node.color else 'lightblue',
                        opacity=0.8,
                        flatshading=True,
                        showlegend=True,  # 레전드에 표시
                        legendgroup=name,  # 같은 그룹으로 묶기
                        hoverinfo='name'  # 호버 시 이름 표시
                    ))

            # 레이아웃 설정 (hide/show + 평면 뷰 버튼 포함)
            fig.update_layout(
                title='3D Model Viewer - Click legend to hide/show components',
                scene=dict(
                    xaxis_title='X',
                    yaxis_title='Y',
                    zaxis_title='Z',
                    aspectmode='data',
                    camera=dict(
                        projection=dict(type='orthographic')
                    )
                ),
                width=1400,
                height=900,
                showlegend=True,
                legend=dict(
                    title=dict(text='Components (Click to hide/show)'),
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255,255,255,0.8)"
                ),
                # XY, YZ, ZX 평면 뷰 버튼 추가
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="left",
                        buttons=[
                            dict(
                                args=[{"scene.camera": dict(
                                    eye=dict(x=0, y=0, z=2),
                                    up=dict(x=0, y=1, z=0),
                                    projection=dict(type='orthographic')
                                )}],
                                label="XY View (Top)",
                                method="relayout"
                            ),
                            dict(
                                args=[{"scene.camera": dict(
                                    eye=dict(x=0, y=-2, z=0),
                                    up=dict(x=0, y=0, z=1),
                                    projection=dict(type='orthographic')
                                )}],
                                label="XZ View (Front)",
                                method="relayout"
                            ),
                            dict(
                                args=[{"scene.camera": dict(
                                    eye=dict(x=2, y=0, z=0),
                                    up=dict(x=0, y=0, z=1),
                                    projection=dict(type='orthographic')
                                )}],
                                label="YZ View (Side)",
                                method="relayout"
                            ),
                            dict(
                                args=[{"scene.camera": dict(
                                    eye=dict(x=1.5, y=1.5, z=1.5),
                                    up=dict(x=0, y=0, z=1),
                                    projection=dict(type='orthographic')
                                )}],
                                label="Isometric",
                                method="relayout"
                            ),
                            dict(
                                args=[{"scene.camera.projection.type": "perspective"}],
                                label="Perspective",
                                method="relayout"
                            ),
                            dict(
                                args=[{"scene.camera.projection.type": "orthographic"}],
                                label="Orthographic",
                                method="relayout"
                            ),
                        ],
                        pad={"r": 10, "t": 10},
                        showactive=True,
                        x=0.5,
                        xanchor="center",
                        y=1.15,
                        yanchor="top"
                    ),
                ]
            )

            # HTML 파일로 저장 (스크립트 위치에)
            html_file = os.path.join(self.script_dir, "3d_viewer.html")
            fig.write_html(html_file, include_plotlyjs=True, full_html=True)

            # 브라우저에서 열기
            import webbrowser
            webbrowser.open(f'file://{html_file}')

            messagebox.showinfo("성공", f"HTML 3D 뷰어가 브라우저에서 열렸습니다.\n파일: {html_file}")

        except Exception as e:
            messagebox.showerror("오류", f"HTML 3D 뷰어 생성 실패:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def open_cadquery_html_viewer(self):
        """CadQuery 네이티브 HTML 뷰어 (jupyter_cadquery 사용)

        기능:
        - Tree view로 hide/show 가능
        - XY, YZ, ZX 평면 뷰
        - 어셈블리 계층 구조 표시
        - 색상 및 투명도 지원
        """
        if not CADQUERY_AVAILABLE:
            messagebox.showerror("오류", "CadQuery가 설치되지 않았습니다.")
            return

        if not JUPYTER_CADQUERY_AVAILABLE:
            messagebox.showerror("오류",
                "jupyter_cadquery가 설치되지 않았습니다.\n"
                "pip install jupyter_cadquery\n\n"
                "jupyter_cadquery를 사용하면 hide/show, XY/YZ/ZX 뷰 등\n"
                "model_checker_3d.py의 모든 기능을 HTML로 사용할 수 있습니다.")
            return

        try:
            # CadQuery Assembly 구조 생성
            assemblies = {}
            assemblies['__ROOT__'] = Assembly(name="ROOT")

            # 1단계: 모든 어셈블리 생성
            for name, node in self.components.items():
                if name == 'root':
                    continue  # Skip internal root
                if node.type == 'assembly':
                    assemblies[name] = Assembly(name=name)

            # 2단계: 형상 추가
            for name, node in self.components.items():
                if name == 'root':
                    continue  # Skip internal root
                if node.type in ['box', 'cyl', 'sphere']:
                    parent_name = node.parent if node.parent else '__ROOT__'
                    if parent_name == 'root':
                        parent_name = '__ROOT__'
                    if parent_name not in assemblies:
                        parent_name = '__ROOT__'

                    parent_assy = assemblies[parent_name]

                    # 형상 생성
                    if node.type == 'box':
                        if node.L <= 0 or node.W <= 0 or node.T <= 0:
                            continue
                        shape = cq.Workplane("XY").box(node.L, node.W, node.T).val()
                        center_z = node.cz + node.T / 2
                    elif node.type == 'cyl':
                        if node.D <= 0 or node.H <= 0:
                            continue
                        shape = cq.Workplane("XY").circle(node.D/2).extrude(node.H).val()
                        shape = shape.translate((0, 0, -node.H/2))
                        center_z = node.cz + node.H / 2
                    elif node.type == 'sphere':
                        if node.D <= 0:
                            continue
                        shape = cq.Workplane("XY").sphere(node.D/2).val()
                        center_z = node.cz + node.D / 2
                    else:
                        continue

                    # 위치 설정 및 어셈블리에 추가
                    loc = Location(Vector(node.cx, node.cy, center_z))
                    color = node.color if node.color else 'lightblue'
                    parent_assy.add(shape, name=name, loc=loc, color=color)

            # 3단계: 어셈블리 계층 구성
            for name, node in self.components.items():
                if name == 'root':
                    continue  # Skip internal root
                if node.type == 'assembly':
                    parent_name = node.parent if node.parent else '__ROOT__'
                    if parent_name == 'root':
                        parent_name = '__ROOT__'
                    if parent_name not in assemblies:
                        parent_name = '__ROOT__'

                    parent_assy = assemblies[parent_name]
                    child_assy = assemblies[name]
                    parent_assy.add(child_assy, name=name)

            root = assemblies['__ROOT__']

            # HTML로 내보내기 (스크립트 위치에)
            html_file = os.path.join(self.script_dir, "cadquery_viewer.html")
            export_success = False

            # jupyter_cadquery의 HTML export 기능 사용 (버전별 호환성 처리)
            # 방법 1: export_html (3.x 버전)
            if hasattr(jcq, 'export_html') and not export_success:
                try:
                    jcq.export_html(
                        root,
                        html_file,
                        axes=False,
                        axes0=False,
                        grid=False,
                        ortho=True,
                        theme='light',
                        default_edgecolor='black',
                        tree_width=250,
                        cad_width=1300,
                        height=700
                    )
                    export_success = True
                except TypeError:
                    # Try without theme parameter
                    try:
                        jcq.export_html(root, html_file)
                        export_success = True
                    except:
                        pass

            # 방법 2: show() with export
            if hasattr(jcq, 'show') and not export_success:
                try:
                    # Try with all parameters first
                    viewer = jcq.show(
                        root,
                        axes=False,
                        axes0=False,
                        grid=False,
                        ortho=True,
                        theme='light'
                    )
                    if hasattr(viewer, 'export_html'):
                        viewer.export_html(html_file)
                        export_success = True
                except TypeError:
                    # Try without theme parameter
                    try:
                        viewer = jcq.show(root, axes=False, grid=False, ortho=True)
                        if hasattr(viewer, 'export_html'):
                            viewer.export_html(html_file)
                            export_success = True
                    except TypeError:
                        # Try with minimal parameters
                        try:
                            viewer = jcq.show(root)
                            if hasattr(viewer, 'export_html'):
                                viewer.export_html(html_file)
                                export_success = True
                        except:
                            pass

            # 방법 3: PartGroup을 통한 export
            if hasattr(jcq, 'PartGroup') and not export_success:
                try:
                    pg = jcq.PartGroup([root])
                    if hasattr(pg, 'to_html'):
                        with open(html_file, 'w') as f:
                            f.write(pg.to_html())
                        export_success = True
                except:
                    pass

            # 방법 4: STEP 파일로 내보내기 (fallback)
            if not export_success:
                # 대체 방법: STEP 파일로 내보내고 three-cad-viewer로 표시
                step_file = os.path.join(self.script_dir, "model.step")
                root.save(step_file)

                # 간단한 HTML 뷰어 생성 (STEP 파일 다운로드 링크 포함)
                html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>CadQuery Model Viewer</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .info {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>CadQuery Model Export</h1>
    <div class="info">
        <p><strong>STEP 파일이 생성되었습니다:</strong> {step_file}</p>
        <p>이 파일을 다음 프로그램에서 열 수 있습니다:</p>
        <ul>
            <li><a href="https://github.com/nickg/cq-editor">CQ-Editor</a> (권장)</li>
            <li>FreeCAD</li>
            <li>온라인: <a href="https://www.3dvieweronline.com/">3D Viewer Online</a></li>
        </ul>
        <p><strong>jupyter_cadquery를 설치하면 완전한 HTML 뷰어를 사용할 수 있습니다:</strong></p>
        <pre>pip install jupyter_cadquery</pre>
    </div>
</body>
</html>'''
                with open(html_file, 'w') as f:
                    f.write(html_content)

                messagebox.showinfo("안내",
                    f"jupyter_cadquery의 HTML export 기능을 찾을 수 없습니다.\n"
                    f"STEP 파일로 내보냈습니다: {step_file}\n\n"
                    f"CQ-Editor 또는 FreeCAD에서 열 수 있습니다.")

            # 브라우저에서 열기
            import webbrowser
            webbrowser.open(f'file://{html_file}')

            messagebox.showinfo("성공",
                f"CadQuery HTML 뷰어가 브라우저에서 열렸습니다.\n"
                f"파일: {html_file}\n\n"
                f"기능:\n"
                f"- Tree view에서 hide/show\n"
                f"- XY, YZ, ZX 평면 뷰\n"
                f"- 마우스로 회전/확대/이동")

        except Exception as e:
            messagebox.showerror("오류", f"CadQuery HTML 뷰어 생성 실패:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _create_shape_for_plotly(self, node: ComponentNode):
        """Plotly용 형상 생성"""
        if node.type == 'box':
            if node.L <= 0 or node.W <= 0 or node.T <= 0:
                return None
            shape = cq.Workplane("XY").box(node.L, node.W, node.T).val()
            center_z = node.cz + node.T / 2
            shape = shape.translate((node.cx, node.cy, center_z))
            return shape

        elif node.type == 'cyl':
            if node.D <= 0 or node.H <= 0:
                return None
            shape = cq.Workplane("XY").circle(node.D/2).extrude(node.H).val()
            center_z = node.cz + node.H / 2
            shape = shape.translate((node.cx, node.cy, center_z - node.H/2))
            return shape

        elif node.type == 'sphere':
            if node.D <= 0:
                return None
            shape = cq.Workplane("XY").sphere(node.D/2).val()
            center_z = node.cz + node.D / 2
            shape = shape.translate((node.cx, node.cy, center_z))
            return shape

        return None

    def _tessellate_for_plotly(self, shape):
        """Plotly용 tessellation (인덱스 기반)"""
        all_vertices = []
        all_triangles = []

        try:
            faces = shape.Faces()

            for face in faces:
                face_data = face.tessellate(0.1)

                if len(face_data) == 2:
                    verts, tris = face_data

                    # Vector를 튜플로 변환
                    verts_list = [v.toTuple() if hasattr(v, 'toTuple') else (v.x, v.y, v.z) for v in verts]

                    # 인덱스 오프셋
                    offset = len(all_vertices)
                    all_vertices.extend(verts_list)

                    # 삼각형 인덱스 추가
                    for tri in tris:
                        all_triangles.append([offset + tri[0], offset + tri[1], offset + tri[2]])

        except Exception as e:
            print(f"Plotly tessellation error: {e}")

        return all_vertices, all_triangles

    def run_3d_viewer(self):
        """3D 뷰어 실행 - Jupyter Notebook 자동 생성 및 실행"""
        csv_file = os.path.join(self.script_dir, "components.csv")
        try:
            # 1. CSV 파일 저장 (스크립트 위치에)
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['name', 'type', 'parent', 'L', 'W', 'T', 'D', 'H',
                             'cx', 'cy', 'cz', 'color', 'coord_file', 'coord_has_header']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for name, node in self.components.items():
                    if name == 'root':
                        continue
                    writer.writerow(node.to_dict())

            # 2. Jupyter Notebook 파일 생성
            notebook_file = self._create_jupyter_notebook()

            # 3. 사용자에게 옵션 제공
            result = messagebox.askyesnocancel(
                "Jupyter 뷰어",
                f"Jupyter Notebook이 생성되었습니다:\n{notebook_file}\n\n"
                f"jupyter_cadquery의 모든 기능을 사용할 수 있습니다:\n"
                f"- Tree view에서 hide/show\n"
                f"- XY, YZ, ZX 평면 뷰\n"
                f"- 어셈블리 계층 구조\n\n"
                f"[예] Jupyter Lab 실행\n"
                f"[아니오] Jupyter Notebook 실행\n"
                f"[취소] 파일만 생성"
            )

            if result is True:  # Jupyter Lab
                import subprocess
                import webbrowser
                # Jupyter Lab 서버 실행
                proc = subprocess.Popen(
                    ['jupyter', 'lab', notebook_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                messagebox.showinfo("안내",
                    f"Jupyter Lab을 실행합니다.\n"
                    f"브라우저에서 notebook이 열립니다.\n\n"
                    f"실행 후 셀을 실행하면 3D 뷰어가 나타납니다.")
            elif result is False:  # Jupyter Notebook
                import subprocess
                proc = subprocess.Popen(
                    ['jupyter', 'notebook', notebook_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                messagebox.showinfo("안내",
                    f"Jupyter Notebook을 실행합니다.\n"
                    f"브라우저에서 notebook이 열립니다.\n\n"
                    f"실행 후 셀을 실행하면 3D 뷰어가 나타납니다.")
            else:  # 취소
                messagebox.showinfo("안내",
                    f"Notebook 파일이 생성되었습니다:\n{notebook_file}\n\n"
                    f"터미널에서 다음 명령으로 실행하세요:\n"
                    f"jupyter lab {notebook_file}")

        except Exception as e:
            messagebox.showerror("오류", f"3D 뷰어 실행 실패:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _create_jupyter_notebook(self):
        """Jupyter Notebook 파일 자동 생성"""
        import json

        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# 3D Model Viewer\n",
                        "GUI에서 자동 생성된 모델을 jupyter_cadquery로 시각화합니다.\n",
                        "\n",
                        "**기능:**\n",
                        "- Tree view에서 hide/show\n",
                        "- XY, YZ, ZX 평면 뷰\n",
                        "- 어셈블리 계층 구조\n",
                        "- 마우스로 회전/확대/이동"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# 자동 생성된 코드 - 아래 셀을 실행하세요\n",
                        "%run model_checker_3d.py"
                    ]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## 수동 실행 (필요시)\n",
                        "위 셀이 작동하지 않으면 아래 코드를 직접 실행하세요."
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": self._generate_viewer_code()
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.8.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }

        notebook_file = os.path.join(self.script_dir, "model_viewer.ipynb")
        with open(notebook_file, 'w', encoding='utf-8') as f:
            json.dump(notebook_content, f, indent=2, ensure_ascii=False)

        return notebook_file

    def _generate_viewer_code(self):
        """jupyter_cadquery 뷰어 코드 생성"""
        code_lines = [
            "import cadquery as cq",
            "from cadquery import Assembly, Location, Vector",
            "import jupyter_cadquery as jcq",
            "",
            "# 어셈블리 구조 생성",
            "assemblies = {}",
            "assemblies['root'] = Assembly(name='ROOT')",
            ""
        ]

        # 어셈블리 생성
        for name, node in self.components.items():
            if name == 'root':
                continue
            if node.type == 'assembly':
                code_lines.append(f"assemblies['{name}'] = Assembly(name='{name}')")

        code_lines.append("")
        code_lines.append("# 형상 추가")

        # assembly 이름 목록 (parent 검증용)
        assembly_names = ['root'] + [n for n, nd in self.components.items() if nd.type == 'assembly']

        # 형상 추가
        for name, node in self.components.items():
            if name == 'root':
                continue
            if node.type in ['box', 'cyl', 'sphere']:
                parent_name = node.parent.name if node.parent else 'root'
                # parent가 assembly가 아니면 root로 fallback
                if parent_name not in assembly_names:
                    parent_name = 'root'

                color = node.color if node.color else 'lightblue'

                if node.type == 'box':
                    center_z = node.cz + node.T / 2
                    code_lines.extend([
                        f"shape = cq.Workplane('XY').box({node.L}, {node.W}, {node.T}).val()",
                        f"loc = Location(Vector({node.cx}, {node.cy}, {center_z}))",
                        f"assemblies['{parent_name}'].add(shape, name='{name}', loc=loc, color='{color}')",
                        ""
                    ])
                elif node.type == 'cyl':
                    center_z = node.cz + node.H / 2
                    code_lines.extend([
                        f"shape = cq.Workplane('XY').circle({node.D/2}).extrude({node.H}).val()",
                        f"shape = shape.translate((0, 0, -{node.H/2}))",
                        f"loc = Location(Vector({node.cx}, {node.cy}, {center_z}))",
                        f"assemblies['{parent_name}'].add(shape, name='{name}', loc=loc, color='{color}')",
                        ""
                    ])
                elif node.type == 'sphere':
                    center_z = node.cz + node.D / 2
                    code_lines.extend([
                        f"shape = cq.Workplane('XY').sphere({node.D/2}).val()",
                        f"loc = Location(Vector({node.cx}, {node.cy}, {center_z}))",
                        f"assemblies['{parent_name}'].add(shape, name='{name}', loc=loc, color='{color}')",
                        ""
                    ])

        # 어셈블리 계층 구성 (위상 정렬: 부모 먼저 연결)
        code_lines.append("# 어셈블리 계층 구성")

        # 위상 정렬을 위한 어셈블리 목록 준비
        assemblies_to_add = []
        for name, node in self.components.items():
            if name == 'root':
                continue
            if node.type == 'assembly':
                parent_name = node.parent.name if node.parent else 'root'
                if parent_name not in assembly_names:
                    parent_name = 'root'
                assemblies_to_add.append((name, parent_name))

        # 위상 정렬: root에 가까운 것부터 추가
        added = set(['root'])
        while assemblies_to_add:
            progress = False
            for assy_name, parent_name in list(assemblies_to_add):
                if parent_name in added:
                    code_lines.append(f"assemblies['{parent_name}'].add(assemblies['{assy_name}'], name='{assy_name}')")
                    added.add(assy_name)
                    assemblies_to_add.remove((assy_name, parent_name))
                    progress = True

            # 무한 루프 방지
            if not progress:
                # 남은 것들은 root에 직접 연결
                for assy_name, parent_name in assemblies_to_add:
                    code_lines.append(f"assemblies['root'].add(assemblies['{assy_name}'], name='{assy_name}')")
                break

        # 뷰어 실행
        code_lines.extend([
            "",
            "# 3D 뷰어 실행",
            "root = assemblies['root']",
            "jcq.show(",
            "    root,",
            "    axes=False,",
            "    axes0=False,",
            "    grid=False,",
            "    ortho=True,",
            "    theme='light',",
            "    default_edgecolor='black',",
            "    tree_width=250,",
            "    cad_width=1300,",
            "    height=700,",
            "    collapse=1",
            ")"
        ])

        return code_lines


def main():
    """메인 함수"""
    root = tk.Tk()
    app = ModelCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
