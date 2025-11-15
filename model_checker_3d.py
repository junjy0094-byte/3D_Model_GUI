import cadquery as cq
from cadquery import Assembly, Location, Vector
import jupyter_cadquery as jcq
import csv
import io
import re
import random

# ============================================================
# 전역 설정
# ============================================================
CSV_FILE = "components.csv"
VERBOSE = False  # True: 로그 출력, False: 로그 숨김

# 랜덤 색상 풀
COLOR_POOL = [
    'lightgray', 'silver', 'darkgray', 'gray',
    'lightblue', 'skyblue', 'steelblue', 'navy',
    'lightgreen', 'limegreen', 'green', 'darkgreen',
    'yellow', 'gold', 'orange', 'darkorange',
    'pink', 'red', 'crimson', 'maroon',
    'violet', 'purple', 'magenta', 'indigo',
    'cyan', 'teal', 'turquoise', 'aquamarine',
    'wheat', 'tan', 'brown', 'chocolate',
    'lavender', 'plum', 'orchid', 'salmon'
]

def log(message):
    """VERBOSE 설정에 따라 로그 출력"""
    if VERBOSE:
        print(message)

def get_random_color():
    """랜덤 색상 반환"""
    return random.choice(COLOR_POOL)

def parse_csv_with_comments(filepath):
    """CSV 파일을 읽어서 빈 줄과 주석을 제거한 후 파싱"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = []
    for line in content.split('\n'):
        if not line.strip():
            continue
        if line.strip().startswith('#'):
            continue
        line = re.sub(r'\s+#.*$', '', line)
        lines.append(line)

    cleaned_content = '\n'.join(lines)
    return list(csv.DictReader(io.StringIO(cleaned_content)))

def parse_pattern_coords(filepath, has_header=True):
    """패턴 좌표 파일 파싱 (콤마, 공백, 탭 구분 모두 지원)"""
    coords = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if i == 0 and has_header:
                continue

            # 콤마, 공백, 탭을 모두 구분자로 인식 (여러 개 연속도 처리)
            tokens = re.split(r'[,\s\t]+', line)
            # 빈 문자열 제거
            tokens = [t for t in tokens if t]

            if len(tokens) >= 2:
                x = float(tokens[0])
                y = float(tokens[1])
                zoff = float(tokens[2]) if len(tokens) >= 3 else 0.0
                coords.append((x, y, zoff))
    return coords

def is_true_value(val):
    """문자열이 True를 의미하는지 확인"""
    if not val or not isinstance(val, str):
        return True
    return val.strip().lower() in ['true', '1', 'yes', 'y']

def create_box(L, W, T):
    """원점 중심 박스 생성"""
    if L <= 0 or W <= 0 or T <= 0:
        raise ValueError(f"Box dimensions must be positive: L={L}, W={W}, T={T}")
    return cq.Workplane("XY").box(L, W, T).val()

def create_cylinder(D, H):
    """원점 중심 원통 생성"""
    if D <= 0 or H <= 0:
        raise ValueError(f"Cylinder dimensions must be positive: D={D}, H={H}")
    shape = cq.Workplane("XY").circle(D/2).extrude(H).val()
    shape = shape.translate((0, 0, -H/2))
    return shape

def create_sphere(D):
    """원점 중심 구 생성"""
    if D <= 0:
        raise ValueError(f"Sphere diameter must be positive: D={D}")
    return cq.Workplane("XY").sphere(D/2).val()

# ============================================================
# 겹침 제거 기능 추가 (위치 고려 버전)
# ============================================================
def remove_overlapping_volumes(shapes_metadata, volume_tol=1e-6):
    """
    겹치는 솔리드들을 자동으로 찾아서 부피가 큰 쪽에서 작은 쪽을 cut합니다.
    실제 배치 위치를 고려하여 겹침을 판단합니다.

    Args:
        shapes_metadata: 딕셔너리 리스트 [{'solid': solid, 'position': (x,y,z), ...}, ...]
        volume_tol: 겹침으로 판단할 최소 부피 (mm³) - 이보다 작으면 단순 접촉으로 간주

    Returns:
        겹침이 제거된 shapes_metadata 리스트 (원점 기준 솔리드로 유지)
    """
    if not shapes_metadata or len(shapes_metadata) < 2:
        return shapes_metadata

    log(f"\n=== 겹침 제거 시작 (총 {len(shapes_metadata)}개 솔리드) ===")

    # 각 솔리드를 실제 위치로 translate한 버전 생성
    positioned_solids = []
    for meta in shapes_metadata:
        solid = meta['solid']
        pos = meta['position']  # (x, y, z) 튜플 (중심 좌표)
        # 실제 위치로 translate
        positioned = solid.translate(pos)
        positioned_solids.append(positioned)

    # 모든 쌍에 대해 검사
    for i in range(len(positioned_solids)):
        for j in range(i + 1, len(positioned_solids)):
            solid_a = positioned_solids[i]
            solid_b = positioned_solids[j]

            if solid_a is None or solid_b is None:
                continue

            try:
                # 1. 바운딩 박스로 빠른 필터링
                bbox_a = solid_a.BoundingBox()
                bbox_b = solid_b.BoundingBox()

                # x, y, z 각 축에서 겹치는지 확인
                x_overlap = not (bbox_a.xmax < bbox_b.xmin or bbox_b.xmax < bbox_a.xmin)
                y_overlap = not (bbox_a.ymax < bbox_b.ymin or bbox_b.ymax < bbox_a.ymin)
                z_overlap = not (bbox_a.zmax < bbox_b.zmin or bbox_b.zmax < bbox_a.zmin)

                if not (x_overlap and y_overlap and z_overlap):
                    # 바운딩 박스가 겹치지 않으면 스킵
                    continue

                # 2. 실제 교집합 계산
                intersection = solid_a.intersect(solid_b)

                if intersection is None:
                    continue

                # 3. 교집합 부피 확인
                try:
                    overlap_volume = intersection.Volume()
                except:
                    overlap_volume = 0.0

                if overlap_volume < volume_tol:
                    # 실제로는 겹치지 않음 (단순 접촉)
                    continue

                # 4. 겹침 발견! 부피 비교
                vol_a = solid_a.Volume()
                vol_b = solid_b.Volume()

                log(f"  겹침 발견: {shapes_metadata[i]['name']} (부피={vol_a:.2f}) vs {shapes_metadata[j]['name']} (부피={vol_b:.2f}), 겹침부피={overlap_volume:.2f}")

                # 5. 큰 쪽에서 작은 쪽을 cut
                if vol_a >= vol_b:
                    # A가 더 크거나 같으면, A에서 B를 깎아냄
                    result = solid_a.cut(solid_b)
                    positioned_solids[i] = result
                    log(f"    → {shapes_metadata[i]['name']}에서 {shapes_metadata[j]['name']}를 제거")
                else:
                    # B가 더 크면, B에서 A를 깎아냄
                    result = solid_b.cut(solid_a)
                    positioned_solids[j] = result
                    log(f"    → {shapes_metadata[j]['name']}에서 {shapes_metadata[i]['name']}를 제거")

                # 참조 업데이트
                solid_a = positioned_solids[i]
                solid_b = positioned_solids[j]

            except Exception as e:
                # Boolean 연산 실패 시 해당 쌍만 스킵
                log(f"  경고: {shapes_metadata[i]['name']}와 {shapes_metadata[j]['name']} 처리 중 오류 발생: {e}")
                continue

    # 결과를 다시 원점 기준으로 변환
    for i, meta in enumerate(shapes_metadata):
        pos = meta['position']
        # 위치 이동의 역변환 (다시 원점으로)
        meta['solid'] = positioned_solids[i].translate((-pos[0], -pos[1], -pos[2]))

    log("=== 겹침 제거 완료 ===\n")
    return shapes_metadata

# ============================================================

log("CSV 파싱 중...")
rows = parse_csv_with_comments(CSV_FILE)

# 유효한 타입들 (형상 타입과 assembly만)
valid_types = ['assembly', 'box', 'cyl', 'sphere']

# 노드 데이터 저장
nodes = {}
name_set = set()

for row in rows:
    name = row.get('name', '').strip()
    node_type = row.get('type', '').strip().lower()

    if not name or node_type not in valid_types:
        continue

    if name in name_set:
        raise ValueError(f"중복된 이름이 발견되었습니다: {name}")
    name_set.add(name)

    parent = row.get('parent', '').strip() or 'root'
    coord_file = row.get('coord_file', '').strip()

    nodes[name] = {
        'type': node_type,
        'parent': parent,
        'L': float(row.get('L', 0) or 0),
        'W': float(row.get('W', 0) or 0),
        'T': float(row.get('T', 0) or 0),
        'D': float(row.get('D', 0) or 0),
        'H': float(row.get('H', 0) or 0),
        'cx': float(row.get('cx', 0) or 0),
        'cy': float(row.get('cy', 0) or 0),
        'cz': float(row.get('cz', 0) or 0),  # 바닥면 높이
        'color': row.get('color', '').strip() or None,
        'coord_file': coord_file,
        'coord_has_header': is_true_value(row.get('coord_has_header', '')),
        'is_pattern': bool(coord_file)  # coord_file이 있으면 패턴
    }

log(f"총 {len(nodes)}개 노드 파싱 완료")

if not nodes:
    raise ValueError("CSV 파일에 유효한 행이 없습니다.")

# 1단계: 모든 어셈블리 객체 생성
log("\n1단계: 어셈블리 생성")
assemblies = {}
assemblies['root'] = Assembly(name="ROOT")
log("  ROOT 생성")

for name, data in nodes.items():
    if data['type'] == 'assembly':
        assemblies[name] = Assembly(name=name)
        log(f"  {name} 생성 (부모: {data['parent']})")

# ============================================================
# 2단계: 모든 Shape 생성 (단일 형상 + Pattern)
# ============================================================
log("\n2단계: 모든 Shape 생성 및 임시 저장")
shapes_metadata = []  # 솔리드와 메타데이터를 저장

for name, data in nodes.items():
    node_type = data['type']

    if node_type in ['box', 'cyl', 'sphere']:
        parent_name = data['parent']

        if parent_name not in assemblies:
            raise ValueError(f"부모 '{parent_name}'를 찾을 수 없습니다 (노드: {name})")

        # 색상 결정: 없으면 랜덤 생성
        color = data['color'] if data['color'] else get_random_color()

        if not data['is_pattern']:
            # 단일 형상
            cz_bottom = data['cz']

            if node_type == 'box':
                shape = create_box(data['L'], data['W'], data['T'])
                center_z = cz_bottom + data['T'] / 2
                log(f"  {name} (box) 생성, 색상={color}")

            elif node_type == 'cyl':
                shape = create_cylinder(data['D'], data['H'])
                center_z = cz_bottom + data['H'] / 2
                log(f"  {name} (cyl) 생성, 색상={color}")

            elif node_type == 'sphere':
                shape = create_sphere(data['D'])
                center_z = cz_bottom + data['D'] / 2
                log(f"  {name} (sphere) 생성, 색상={color}")

            # 메타데이터와 함께 저장
            shapes_metadata.append({
                'name': name,
                'solid': shape,
                'parent': parent_name,
                'position': (data['cx'], data['cy'], center_z),
                'loc': Location(Vector(data['cx'], data['cy'], center_z)),
                'color': color,
                'is_pattern': False
            })

        else:
            # Pattern: 모든 아이템을 하나의 solid로 합침
            coords = parse_pattern_coords(data['coord_file'], data['coord_has_header'])

            # 패턴의 오프셋
            offset_x = data['cx']
            offset_y = data['cy']
            offset_z_bottom = data['cz']

            # 모든 패턴 아이템을 생성하여 실제 위치로 translate
            pattern_items = []
            for idx, (x, y, zoff) in enumerate(coords):
                if node_type == 'box':
                    item = create_box(data['L'], data['W'], data['T'])
                    center_z = offset_z_bottom + data['T'] / 2 + zoff
                elif node_type == 'cyl':
                    item = create_cylinder(data['D'], data['H'])
                    center_z = offset_z_bottom + data['H'] / 2 + zoff
                elif node_type == 'sphere':
                    item = create_sphere(data['D'])
                    center_z = offset_z_bottom + data['D'] / 2 + zoff

                # 실제 위치로 translate
                item_positioned = item.translate((x + offset_x, y + offset_y, center_z))
                pattern_items.append(item_positioned)

            # 모든 아이템을 하나의 solid로 합침 (fuse)
            if len(pattern_items) > 0:
                fused_solid = pattern_items[0]
                for item in pattern_items[1:]:
                    fused_solid = fused_solid.fuse(item)

                # 합쳐진 solid를 원점 기준으로 저장 (이미 위치 적용됨)
                # position은 (0,0,0)으로 설정 (이미 translate되어 있음)
                shapes_metadata.append({
                    'name': name,
                    'solid': fused_solid,
                    'parent': parent_name,
                    'position': (0, 0, 0),  # 이미 translate되어 있음
                    'loc': Location(Vector(0, 0, 0)),
                    'color': color,
                    'is_pattern': True
                })
                log(f"  {name} (pattern {node_type}, {len(coords)}개) 생성 및 합침, 색상={color}")

# ============================================================
# 겹침 제거 실행 (위치 고려)
# ============================================================
if len(shapes_metadata) > 0:
    log(f"\n겹침 검사 대상: {len(shapes_metadata)}개 솔리드")
    shapes_metadata = remove_overlapping_volumes(shapes_metadata, volume_tol=1e-6)

# ============================================================
# 겹침 제거된 Shape들을 어셈블리에 추가
# ============================================================
log("\n3단계: 겹침 제거된 Shape 추가")
for meta in shapes_metadata:
    parent_assy = assemblies[meta['parent']]
    parent_assy.add(meta['solid'], name=meta['name'], loc=meta['loc'], color=meta['color'])
    type_desc = "pattern" if meta['is_pattern'] else "shape"
    log(f"  {meta['parent']} <- {meta['name']} ({type_desc}, 색상: {meta['color']})")

# ============================================================
# 4단계: 어셈블리 계층 구성
# ============================================================
log("\n4단계: 어셈블리 계층 구성")
for name, data in nodes.items():
    if data['type'] == 'assembly':
        parent_name = data['parent']

        if parent_name not in assemblies:
            raise ValueError(f"부모 '{parent_name}'를 찾을 수 없습니다 (어셈블리: {name})")

        parent_assy = assemblies[parent_name]
        child_assy = assemblies[name]

        parent_assy.add(child_assy, name=name)
        log(f"  {parent_name} <- {name} (assembly)")

# 최종 표시
log("\n렌더링 중...")
root = assemblies['root']
jcq.show(
    root,
    axes=False,
    axes0=False,
    grid=False,
    ortho=True,
    theme='light',
    default_edgecolor='black',
    tree_width=250,
    cad_width=1300,
    height=700,
    collapse=1
)
log("완료!")
