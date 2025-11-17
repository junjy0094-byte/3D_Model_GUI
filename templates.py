"""
PCB Assembly Template System

PCB 스택업 구조를 쉽게 생성하기 위한 템플릿 시스템
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Any


class PCBStackupTemplate:
    """PCB 스택업 템플릿 (Geometry A)"""

    def __init__(self, parent_window, callback):
        self.parent = parent_window
        self.callback = callback  # 컴포넌트 생성 콜백
        self.window = None

        # PCB 레이어 변수들
        self.layer_vars = {}
        self.size_vars = {}

    def show_dialog(self):
        """템플릿 다이얼로그 표시"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("PCB 스택업 템플릿 (Geometry A)")
        self.window.geometry("600x700")
        self.window.transient(self.parent)
        self.window.grab_set()

        # 메인 프레임
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 설명
        ttk.Label(main_frame, text="PCB 스택업 구조 생성", font=('', 12, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text="각 레이어의 크기와 두께를 입력하세요. 자동으로 스택업됩니다.").pack(pady=(0, 10))

        # PCB 기본 크기
        size_frame = ttk.LabelFrame(main_frame, text="PCB 기본 크기", padding=10)
        size_frame.pack(fill=tk.X, pady=5)

        ttk.Label(size_frame, text="L (길이):").grid(row=0, column=0, sticky='w', padx=5)
        self.pcb_L_var = tk.DoubleVar(value=100.0)
        ttk.Entry(size_frame, textvariable=self.pcb_L_var, width=15).grid(row=0, column=1, padx=5)

        ttk.Label(size_frame, text="W (너비):").grid(row=0, column=2, sticky='w', padx=5)
        self.pcb_W_var = tk.DoubleVar(value=100.0)
        ttk.Entry(size_frame, textvariable=self.pcb_W_var, width=15).grid(row=0, column=3, padx=5)

        # 레이어 설정 (스크롤 가능)
        layers_frame = ttk.LabelFrame(main_frame, text="레이어 설정", padding=10)
        layers_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 스크롤 가능한 캔버스
        canvas = tk.Canvas(layers_frame)
        scrollbar = ttk.Scrollbar(layers_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 레이어 목록 생성
        self._create_layer_inputs(scrollable_frame)

        # 칩 설정
        chip_frame = ttk.LabelFrame(main_frame, text="칩 설정 (선택)", padding=10)
        chip_frame.pack(fill=tk.X, pady=5)

        self.add_chip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(chip_frame, text="칩 추가", variable=self.add_chip_var).grid(row=0, column=0, sticky='w', pady=2)

        ttk.Label(chip_frame, text="L:").grid(row=1, column=0, sticky='w', padx=5)
        self.chip_L_var = tk.DoubleVar(value=10.0)
        ttk.Entry(chip_frame, textvariable=self.chip_L_var, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(chip_frame, text="W:").grid(row=1, column=2, sticky='w', padx=5)
        self.chip_W_var = tk.DoubleVar(value=10.0)
        ttk.Entry(chip_frame, textvariable=self.chip_W_var, width=10).grid(row=1, column=3, padx=5)

        ttk.Label(chip_frame, text="T:").grid(row=1, column=4, sticky='w', padx=5)
        self.chip_T_var = tk.DoubleVar(value=2.0)
        ttk.Entry(chip_frame, textvariable=self.chip_T_var, width=10).grid(row=1, column=5, padx=5)

        # 솔더볼 설정
        solder_frame = ttk.LabelFrame(main_frame, text="솔더볼 설정 (선택)", padding=10)
        solder_frame.pack(fill=tk.X, pady=5)

        self.add_solder_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(solder_frame, text="솔더볼 추가", variable=self.add_solder_var).grid(row=0, column=0, sticky='w', pady=2)

        ttk.Label(solder_frame, text="D (직경):").grid(row=1, column=0, sticky='w', padx=5)
        self.solder_D_var = tk.DoubleVar(value=0.5)
        ttk.Entry(solder_frame, textvariable=self.solder_D_var, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(solder_frame, text="Grid (NxN):").grid(row=1, column=2, sticky='w', padx=5)
        self.solder_grid_var = tk.IntVar(value=5)
        ttk.Entry(solder_frame, textvariable=self.solder_grid_var, width=10).grid(row=1, column=3, padx=5)

        ttk.Label(solder_frame, text="Pitch:").grid(row=1, column=4, sticky='w', padx=5)
        self.solder_pitch_var = tk.DoubleVar(value=1.0)
        ttk.Entry(solder_frame, textvariable=self.solder_pitch_var, width=10).grid(row=1, column=5, padx=5)

        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="생성", command=self.generate_stackup, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", command=self.window.destroy, width=15).pack(side=tk.LEFT, padx=5)

    def _create_layer_inputs(self, parent):
        """레이어 입력 필드 생성"""
        # 헤더
        ttk.Label(parent, text="활성화", font=('', 9, 'bold')).grid(row=0, column=0, padx=5)
        ttk.Label(parent, text="레이어", font=('', 9, 'bold')).grid(row=0, column=1, padx=5)
        ttk.Label(parent, text="두께 (T)", font=('', 9, 'bold')).grid(row=0, column=2, padx=5)
        ttk.Label(parent, text="색상", font=('', 9, 'bold')).grid(row=0, column=3, padx=5)

        # 레이어 정의 (이름, 기본 활성화, 기본 두께, 기본 색상)
        layers = [
            ('cu1', True, 0.035, 'gold'),
            ('ppg1', True, 0.2, 'lightgreen'),
            ('cu2', True, 0.035, 'gold'),
            ('ppg2', True, 0.2, 'lightgreen'),
            ('cu3', True, 0.035, 'gold'),
            ('ppg3', True, 0.2, 'lightgreen'),
            ('cu4', False, 0.035, 'gold'),
            ('ppg4', False, 0.2, 'lightgreen'),
            ('cu5', False, 0.035, 'gold'),
            ('ppg5', False, 0.2, 'lightgreen'),
            ('cu6', False, 0.035, 'gold'),
            ('ppg6', False, 0.2, 'lightgreen'),
        ]

        for idx, (name, enabled, thickness, color) in enumerate(layers, start=1):
            # 활성화 체크박스
            enabled_var = tk.BooleanVar(value=enabled)
            ttk.Checkbutton(parent, variable=enabled_var).grid(row=idx, column=0, padx=5, pady=2)
            self.layer_vars[f'{name}_enabled'] = enabled_var

            # 레이어 이름
            ttk.Label(parent, text=name).grid(row=idx, column=1, padx=5, pady=2)

            # 두께
            thickness_var = tk.DoubleVar(value=thickness)
            ttk.Entry(parent, textvariable=thickness_var, width=10).grid(row=idx, column=2, padx=5, pady=2)
            self.layer_vars[f'{name}_thickness'] = thickness_var

            # 색상
            color_var = tk.StringVar(value=color)
            ttk.Entry(parent, textvariable=color_var, width=12).grid(row=idx, column=3, padx=5, pady=2)
            self.layer_vars[f'{name}_color'] = color_var

    def generate_stackup(self):
        """스택업 구조 생성"""
        components = []

        L = self.pcb_L_var.get()
        W = self.pcb_W_var.get()

        current_z = 0.0  # 현재 Z 위치 (바닥면)

        # PCB 어셈블리 생성
        components.append({
            'name': 'PCB_Assembly',
            'type': 'assembly',
            'parent': 'root',
            'L': 0, 'W': 0, 'T': 0, 'D': 0, 'H': 0,
            'cx': 0, 'cy': 0, 'cz': 0,
            'color': '', 'coord_file': '', 'coord_has_header': True
        })

        # 레이어 생성 (아래에서 위로)
        layer_names = ['cu1', 'ppg1', 'cu2', 'ppg2', 'cu3', 'ppg3',
                      'cu4', 'ppg4', 'cu5', 'ppg5', 'cu6', 'ppg6']

        for layer_name in layer_names:
            if not self.layer_vars[f'{layer_name}_enabled'].get():
                continue

            thickness = self.layer_vars[f'{layer_name}_thickness'].get()
            color = self.layer_vars[f'{layer_name}_color'].get()

            components.append({
                'name': layer_name,
                'type': 'box',
                'parent': 'PCB_Assembly',
                'L': L, 'W': W, 'T': thickness,
                'D': 0, 'H': 0,
                'cx': 0, 'cy': 0, 'cz': current_z,
                'color': color,
                'coord_file': '', 'coord_has_header': True
            })

            current_z += thickness

        # 솔더볼 추가
        if self.add_solder_var.get():
            solder_d = self.solder_D_var.get()
            grid_size = self.solder_grid_var.get()
            pitch = self.solder_pitch_var.get()

            # 솔더볼 어셈블리
            components.append({
                'name': 'Solder_Balls',
                'type': 'assembly',
                'parent': 'PCB_Assembly',
                'L': 0, 'W': 0, 'T': 0, 'D': 0, 'H': 0,
                'cx': 0, 'cy': 0, 'cz': 0,
                'color': '', 'coord_file': '', 'coord_has_header': True
            })

            # 솔더볼 그리드 생성
            total_width = (grid_size - 1) * pitch
            start_offset = -total_width / 2

            ball_idx = 1
            for i in range(grid_size):
                for j in range(grid_size):
                    x = start_offset + i * pitch
                    y = start_offset + j * pitch

                    components.append({
                        'name': f'solder_ball_{ball_idx}',
                        'type': 'sphere',
                        'parent': 'Solder_Balls',
                        'L': 0, 'W': 0, 'T': 0,
                        'D': solder_d, 'H': 0,
                        'cx': x, 'cy': y, 'cz': current_z,
                        'color': 'silver',
                        'coord_file': '', 'coord_has_header': True
                    })
                    ball_idx += 1

            # 솔더볼 높이만큼 Z 이동
            current_z += solder_d

        # 칩 추가
        if self.add_chip_var.get():
            chip_L = self.chip_L_var.get()
            chip_W = self.chip_W_var.get()
            chip_T = self.chip_T_var.get()

            components.append({
                'name': 'Chip',
                'type': 'box',
                'parent': 'PCB_Assembly',
                'L': chip_L, 'W': chip_W, 'T': chip_T,
                'D': 0, 'H': 0,
                'cx': 0, 'cy': 0, 'cz': current_z,
                'color': 'gray',
                'coord_file': '', 'coord_has_header': True
            })

        # 콜백으로 컴포넌트 전달
        self.callback(components)

        self.window.destroy()
        messagebox.showinfo("성공", f"{len(components)}개 컴포넌트가 생성되었습니다.")


# 추가 템플릿을 위한 클래스들 (향후 확장)

class TemplateManager:
    """템플릿 관리자"""

    def __init__(self, parent_window, callback):
        self.parent = parent_window
        self.callback = callback

        # 사용 가능한 템플릿
        self.templates = {
            'A': ('PCB 스택업 (Geometry A)', PCBStackupTemplate),
            # 향후 추가:
            # 'B': ('BGA Package (Geometry B)', BGAPackageTemplate),
            # 'C': ('Wire Bonding (Geometry C)', WireBondingTemplate),
            # 'D': ('Flip Chip (Geometry D)', FlipChipTemplate),
        }

    def show_selector(self):
        """템플릿 선택 다이얼로그"""
        window = tk.Toplevel(self.parent)
        window.title("템플릿 선택")
        window.geometry("400x300")
        window.transient(self.parent)
        window.grab_set()

        ttk.Label(window, text="템플릿을 선택하세요", font=('', 12, 'bold')).pack(pady=10)

        # 템플릿 목록
        for key, (name, template_class) in self.templates.items():
            btn = ttk.Button(
                window,
                text=f"{key}: {name}",
                command=lambda tc=template_class, w=window: self._open_template(tc, w),
                width=40
            )
            btn.pack(pady=5)

        # 향후 추가될 템플릿 안내
        ttk.Separator(window, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(window, text="향후 추가 예정:", font=('', 9, 'italic')).pack()
        ttk.Label(window, text="B: BGA Package").pack()
        ttk.Label(window, text="C: Wire Bonding").pack()
        ttk.Label(window, text="D: Flip Chip").pack()

        ttk.Button(window, text="닫기", command=window.destroy).pack(pady=10)

    def _open_template(self, template_class, selector_window):
        """템플릿 다이얼로그 열기"""
        selector_window.destroy()
        template = template_class(self.parent, self.callback)
        template.show_dialog()
