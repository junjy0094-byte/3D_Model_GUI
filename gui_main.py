#!/usr/bin/env python3
"""
3D Model Checker GUI
Assembly 구조를 GUI로 편집하고 CSV로 저장하는 도구
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os

class ComponentNode:
    """컴포넌트 트리 노드"""
    def __init__(self, name, node_type='assembly', parent=None):
        self.name = name
        self.type = node_type  # assembly, box, cyl, sphere
        self.parent = parent
        self.children = []

        # 형상 파라미터
        self.L = 0.0  # Box: Length
        self.W = 0.0  # Box: Width
        self.T = 0.0  # Box: Thickness
        self.D = 0.0  # Cylinder/Sphere: Diameter
        self.H = 0.0  # Cylinder: Height

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
        self.children.append(child)
        child.parent = self

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


class ModelCheckerGUI:
    """3D Model Checker GUI 메인 클래스"""

    def __init__(self, root):
        self.root = root
        self.root.title("3D Model Checker GUI")
        self.root.geometry("1000x700")

        # 루트 노드 (항상 존재)
        self.root_node = ComponentNode('root', 'assembly')
        self.components = {'root': self.root_node}  # name -> ComponentNode

        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임 (좌우 분할)
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 좌측: 트리 뷰
        left_frame = ttk.LabelFrame(main_frame, text="Assembly 구조", padding=5)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))

        # 우측: 입력 폼
        right_frame = ttk.LabelFrame(main_frame, text="컴포넌트 추가/편집", padding=5)
        right_frame.grid(row=0, column=1, sticky='nsew')

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # === 좌측 트리 뷰 ===
        self.setup_tree_view(left_frame)

        # === 우측 입력 폼 ===
        self.setup_input_form(right_frame)

        # === 하단 버튼 ===
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_frame, text="CSV 저장", command=self.save_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="CSV 불러오기", command=self.load_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="3D 뷰어 실행", command=self.run_3d_viewer).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="종료", command=self.root.quit).pack(side=tk.RIGHT, padx=2)

    def setup_tree_view(self, parent):
        """트리 뷰 설정"""
        # 스크롤바
        tree_scroll = ttk.Scrollbar(parent)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 트리 뷰
        self.tree = ttk.Treeview(parent, yscrollcommand=tree_scroll.set, selectmode='browse')
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        # 컬럼 설정
        self.tree['columns'] = ('type', 'dimensions')
        self.tree.column('#0', width=200, minwidth=150)
        self.tree.column('type', width=80, minwidth=50)
        self.tree.column('dimensions', width=150, minwidth=100)

        self.tree.heading('#0', text='이름')
        self.tree.heading('type', text='타입')
        self.tree.heading('dimensions', text='치수')

        # ROOT 추가
        self.tree.insert('', 'end', 'root', text='ROOT', values=('assembly', ''), open=True)

        # 선택 이벤트
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # 우클릭 메뉴
        self.tree.bind('<Button-3>', self.show_context_menu)

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
        ttk.Label(form, text="이름:").grid(row=row, column=0, sticky='w', pady=2)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=30).grid(row=row, column=1, sticky='ew', pady=2)
        row += 1

        # 타입
        ttk.Label(form, text="타입:").grid(row=row, column=0, sticky='w', pady=2)
        self.type_var = tk.StringVar(value='box')
        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky='w', pady=2)
        ttk.Radiobutton(type_frame, text='Assembly', variable=self.type_var,
                       value='assembly', command=self.on_type_change).pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text='Box', variable=self.type_var,
                       value='box', command=self.on_type_change).pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text='Cylinder', variable=self.type_var,
                       value='cyl', command=self.on_type_change).pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text='Sphere', variable=self.type_var,
                       value='sphere', command=self.on_type_change).pack(side=tk.LEFT)
        row += 1

        # 부모 선택
        ttk.Label(form, text="부모:").grid(row=row, column=0, sticky='w', pady=2)
        self.parent_var = tk.StringVar(value='root')
        self.parent_combo = ttk.Combobox(form, textvariable=self.parent_var, width=28)
        self.parent_combo.grid(row=row, column=1, sticky='ew', pady=2)
        self.update_parent_combo()
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 형상 파라미터 ===
        ttk.Label(form, text="형상 파라미터", font=('', 9, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        row += 1

        # Box 파라미터
        self.box_frame = ttk.LabelFrame(form, text="Box")
        self.L_var = tk.DoubleVar(value=0.0)
        self.W_var = tk.DoubleVar(value=0.0)
        self.T_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.box_frame, text="L (길이):").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.L_var, width=15).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.box_frame, text="W (너비):").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.W_var, width=15).grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Label(self.box_frame, text="T (두께):").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(self.box_frame, textvariable=self.T_var, width=15).grid(row=2, column=1, sticky='ew', pady=2)

        # Cylinder 파라미터
        self.cyl_frame = ttk.LabelFrame(form, text="Cylinder")
        self.D_cyl_var = tk.DoubleVar(value=0.0)
        self.H_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.cyl_frame, text="D (직경):").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.cyl_frame, textvariable=self.D_cyl_var, width=15).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.cyl_frame, text="H (높이):").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.cyl_frame, textvariable=self.H_var, width=15).grid(row=1, column=1, sticky='ew', pady=2)

        # Sphere 파라미터
        self.sphere_frame = ttk.LabelFrame(form, text="Sphere")
        self.D_sphere_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.sphere_frame, text="D (직경):").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.sphere_frame, textvariable=self.D_sphere_var, width=15).grid(row=0, column=1, sticky='ew', pady=2)

        # 형상 프레임 배치 (초기: box만 표시)
        self.box_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 위치 파라미터 ===
        ttk.Label(form, text="위치 파라미터", font=('', 9, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        row += 1

        self.position_frame = ttk.Frame(form)
        self.cx_var = tk.DoubleVar(value=0.0)
        self.cy_var = tk.DoubleVar(value=0.0)
        self.cz_var = tk.DoubleVar(value=0.0)

        ttk.Label(self.position_frame, text="cx (X):").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cx_var, width=15).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(self.position_frame, text="cy (Y):").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cy_var, width=15).grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Label(self.position_frame, text="cz (Z 바닥):").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(self.position_frame, textvariable=self.cz_var, width=15).grid(row=2, column=1, sticky='ew', pady=2)

        self.position_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        ttk.Separator(form, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=5)
        row += 1

        # === 기타 ===
        ttk.Label(form, text="색상 (선택):").grid(row=row, column=0, sticky='w', pady=2)
        self.color_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.color_var, width=30).grid(row=row, column=1, sticky='ew', pady=2)
        row += 1

        ttk.Label(form, text="좌표 파일 (패턴):").grid(row=row, column=0, sticky='w', pady=2)
        coord_frame = ttk.Frame(form)
        coord_frame.grid(row=row, column=1, sticky='ew', pady=2)
        self.coord_file_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.coord_file_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(coord_frame, text="찾기", command=self.browse_coord_file, width=5).pack(side=tk.LEFT, padx=(2, 0))
        row += 1

        self.coord_header_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="좌표 파일 헤더 있음", variable=self.coord_header_var).grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        # 버튼
        button_frame = ttk.Frame(form)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="추가", command=self.add_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="수정", command=self.update_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="삭제", command=self.delete_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="초기화", command=self.clear_form).pack(side=tk.LEFT, padx=5)

        # 초기 타입 변경
        self.on_type_change()

    def on_type_change(self):
        """타입 변경 시 적절한 파라미터 프레임 표시"""
        node_type = self.type_var.get()

        # 모든 프레임 숨김
        self.box_frame.grid_remove()
        self.cyl_frame.grid_remove()
        self.sphere_frame.grid_remove()
        self.position_frame.grid_remove()

        # 타입에 따라 적절한 프레임 표시
        if node_type == 'box':
            self.box_frame.grid()
            self.position_frame.grid()
        elif node_type == 'cyl':
            self.cyl_frame.grid()
            self.position_frame.grid()
        elif node_type == 'sphere':
            self.sphere_frame.grid()
            self.position_frame.grid()
        # assembly는 위치 파라미터 불필요

    def browse_coord_file(self):
        """좌표 파일 찾기"""
        filename = filedialog.askopenfilename(
            title="좌표 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )
        if filename:
            self.coord_file_var.set(filename)

    def update_parent_combo(self):
        """부모 콤보박스 업데이트 (assembly만 표시)"""
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
        if parent_name not in self.components:
            messagebox.showerror("오류", f"부모 '{parent_name}'을(를) 찾을 수 없습니다.")
            return

        # 노드 생성
        node = ComponentNode(name, self.type_var.get(), self.components[parent_name])

        # 파라미터 설정
        node.L = self.L_var.get()
        node.W = self.W_var.get()
        node.T = self.T_var.get()

        if node.type == 'cyl':
            node.D = self.D_cyl_var.get()
            node.H = self.H_var.get()
        elif node.type == 'sphere':
            node.D = self.D_sphere_var.get()

        node.cx = self.cx_var.get()
        node.cy = self.cy_var.get()
        node.cz = self.cz_var.get()
        node.color = self.color_var.get()
        node.coord_file = self.coord_file_var.get()
        node.coord_has_header = self.coord_header_var.get()

        # 트리에 추가
        self.components[name] = node
        self.components[parent_name].add_child(node)

        # 트리뷰 업데이트
        dimensions = self.get_dimension_str(node)
        self.tree.insert(parent_name, 'end', name, text=name, values=(node.type, dimensions))

        # 부모 콤보박스 업데이트
        self.update_parent_combo()

        messagebox.showinfo("성공", f"'{name}' 추가됨")
        self.clear_form()

    def update_component(self):
        """선택된 컴포넌트 수정"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("오류", "수정할 컴포넌트를 선택하세요.")
            return

        item_id = selection[0]
        if item_id == 'root':
            messagebox.showerror("오류", "ROOT는 수정할 수 없습니다.")
            return

        node = self.components[item_id]

        # 파라미터 업데이트
        node.type = self.type_var.get()
        node.L = self.L_var.get()
        node.W = self.W_var.get()
        node.T = self.T_var.get()

        if node.type == 'cyl':
            node.D = self.D_cyl_var.get()
            node.H = self.H_var.get()
        elif node.type == 'sphere':
            node.D = self.D_sphere_var.get()

        node.cx = self.cx_var.get()
        node.cy = self.cy_var.get()
        node.cz = self.cz_var.get()
        node.color = self.color_var.get()
        node.coord_file = self.coord_file_var.get()
        node.coord_has_header = self.coord_header_var.get()

        # 트리뷰 업데이트
        dimensions = self.get_dimension_str(node)
        self.tree.item(item_id, values=(node.type, dimensions))

        messagebox.showinfo("성공", f"'{item_id}' 수정됨")

    def delete_component(self):
        """선택된 컴포넌트 삭제"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("오류", "삭제할 컴포넌트를 선택하세요.")
            return

        item_id = selection[0]
        if item_id == 'root':
            messagebox.showerror("오류", "ROOT는 삭제할 수 없습니다.")
            return

        if messagebox.askyesno("확인", f"'{item_id}'를 삭제하시겠습니까?"):
            # 자식도 함께 삭제
            self.delete_recursive(item_id)
            self.tree.delete(item_id)
            self.update_parent_combo()
            messagebox.showinfo("성공", f"'{item_id}' 삭제됨")
            self.clear_form()

    def delete_recursive(self, name):
        """재귀적으로 노드와 자식들 삭제"""
        if name not in self.components:
            return

        node = self.components[name]
        for child in list(node.children):
            self.delete_recursive(child.name)

        if node.parent:
            node.parent.children.remove(node)

        del self.components[name]

    def on_tree_select(self, event):
        """트리 선택 시 폼에 값 로드"""
        selection = self.tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id not in self.components:
            return

        node = self.components[item_id]

        # 폼에 값 로드
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
        """노드의 치수 문자열 반환"""
        if node.type == 'assembly':
            return ''
        elif node.type == 'box':
            return f"L={node.L}, W={node.W}, T={node.T}"
        elif node.type == 'cyl':
            return f"D={node.D}, H={node.H}"
        elif node.type == 'sphere':
            return f"D={node.D}"
        return ''

    def show_context_menu(self, event):
        """우클릭 메뉴 (추후 확장 가능)"""
        pass

    def save_csv(self):
        """CSV 파일로 저장"""
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

                # root는 제외하고 저장
                for name, node in self.components.items():
                    if name == 'root':
                        continue
                    writer.writerow(node.to_dict())

            messagebox.showinfo("성공", f"CSV 파일 저장됨:\n{filename}")
        except Exception as e:
            messagebox.showerror("오류", f"CSV 저장 실패:\n{str(e)}")

    def load_csv(self):
        """CSV 파일 불러오기"""
        filename = filedialog.askopenfilename(
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )

        if not filename:
            return

        try:
            # 기존 데이터 초기화 (root 제외)
            for name in list(self.components.keys()):
                if name != 'root':
                    del self.components[name]

            self.root_node.children = []

            # 트리뷰 초기화
            for item in self.tree.get_children('root'):
                self.tree.delete(item)

            # CSV 읽기
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # 먼저 assembly 생성
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

            # 나머지 컴포넌트 생성
            for row in rows:
                node_type = row['type'].strip().lower()
                if node_type == 'assembly':
                    continue

                name = row['name'].strip()
                parent_name = row.get('parent', '').strip() or 'root'

                if parent_name not in self.components:
                    continue

                node = ComponentNode(name, node_type, self.components[parent_name])

                # 파라미터 설정
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
            messagebox.showinfo("성공", f"CSV 파일 불러옴:\n{filename}")

        except Exception as e:
            messagebox.showerror("오류", f"CSV 불러오기 실패:\n{str(e)}")

    def run_3d_viewer(self):
        """3D 뷰어 실행"""
        # 먼저 CSV 저장
        csv_file = "components.csv"
        try:
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['name', 'type', 'parent', 'L', 'W', 'T', 'D', 'H',
                             'cx', 'cy', 'cz', 'color', 'coord_file', 'coord_has_header']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for name, node in self.components.items():
                    if name == 'root':
                        continue
                    writer.writerow(node.to_dict())

            # 3D 뷰어 실행 (별도 프로세스로)
            import subprocess
            subprocess.Popen(['python3', 'model_checker_3d.py'])

            messagebox.showinfo("정보", "3D 뷰어를 실행합니다.\n(jupyter 환경에서 실행하세요)")

        except Exception as e:
            messagebox.showerror("오류", f"3D 뷰어 실행 실패:\n{str(e)}")


def main():
    """메인 함수"""
    root = tk.Tk()
    app = ModelCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
