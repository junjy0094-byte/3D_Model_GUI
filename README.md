# 3D Model Checker GUI (Enhanced)

3D Assembly 구조를 GUI로 편집하고 CSV로 저장한 뒤 3D로 시각화하는 통합 도구입니다.

## 주요 기능

### ✨ 새로운 기능 (Enhanced Version)

- **🎨 GUI 내장 3D 미리보기**: Jupyter 없이도 GUI 내에서 바로 3D 모델 확인
- **↔️ 드래그 앤 드롭**: 트리 뷰에서 드래그 앤 드롭으로 계층 구조 변경
- **↶↷ Undo/Redo**: 모든 작업을 취소/재실행 가능 (최대 50단계)
- **⌨️ 키보드 단축키**:
  - `Ctrl+Z`: Undo
  - `Ctrl+Y`: Redo
  - `Ctrl+S`: CSV 저장
  - `Ctrl+O`: CSV 불러오기
  - `F5`: 3D 미리보기 새로고침
- **📐 3분할 레이아웃**: 트리 뷰 | 3D 미리보기 | 편집 폼

### 🔧 기본 기능

- **GUI 기반 Assembly 편집**: CSV 파일을 직접 편집하는 대신 GUI로 편리하게 작성
- **계층 구조 관리**: Assembly와 Part를 트리 구조로 관리
- **다양한 형상 지원**: Box, Cylinder, Sphere
- **패턴 배치**: 좌표 파일을 이용한 반복 패턴 지원
- **CSV 저장/불러오기**: 기존 CSV와 호환
- **3D 뷰어 통합**: CadQuery + jupyter_cadquery로 고급 시각화 (선택적)

## 설치

```bash
# 의존성 설치
pip install -r requirements.txt
```

## 사용법

### 1. GUI 실행

```bash
python3 gui_main.py
```

### 2. 컴포넌트 추가 및 편집

#### 추가하기
1. 우측 패널에서 **이름** 입력
2. **타입** 선택 (Assembly, Box, Cylinder, Sphere)
3. **부모** 선택 (계층 구조)
4. **형상 파라미터** 입력
   - Box: L (길이), W (너비), T (두께)
   - Cylinder: D (직경), H (높이)
   - Sphere: D (직경)
5. **위치 파라미터** 입력
   - cx, cy: X, Y 좌표
   - cz: Z 바닥면 높이
6. **(선택) 색상** 입력 (예: lightblue, red, #FF5733)
7. **(선택) 좌표 파일** 선택 (패턴 배치용)
8. **추가** 버튼 클릭
9. **F5** 키를 눌러 3D 미리보기 새로고침

#### 수정하기
1. 좌측 트리에서 컴포넌트 선택
2. 우측 패널에서 값 수정
3. **수정** 버튼 클릭
4. 자동으로 3D 미리보기 업데이트

#### 삭제하기
1. 좌측 트리에서 컴포넌트 선택
2. 좌측 상단 **🗑 삭제** 버튼 클릭 (또는 우측 패널의 삭제 버튼)

#### 계층 구조 변경 (드래그 앤 드롭)
1. 좌측 트리에서 이동할 컴포넌트를 클릭
2. 드래그하여 새 부모 Assembly로 드롭
3. 자동으로 계층 구조 업데이트 및 Undo 히스토리에 저장

### 3. Undo/Redo

- **Ctrl+Z**: 마지막 작업 취소
- **Ctrl+Y**: 취소한 작업 재실행
- 좌측 상단의 **↶ Undo**, **↷ Redo** 버튼으로도 가능
- 최대 50단계까지 Undo 가능

### 4. 3D 미리보기

- **중앙 패널**에서 실시간으로 3D 모델 확인
- **F5** 키 또는 우측 하단 **🔄 3D 새로고침** 버튼으로 업데이트
- 마우스로 회전, 확대/축소 가능 (matplotlib 툴바 사용)
- 컴포넌트 추가/수정/삭제 시 자동 업데이트

### 5. CSV 저장/불러오기

- **Ctrl+S** 또는 하단 **💾 CSV 저장** 버튼: 파일로 저장
- **Ctrl+O** 또는 하단 **📂 CSV 불러오기** 버튼: 파일에서 불러오기
- 불러오기 시 자동으로 3D 미리보기 업데이트

### 6. 고급 3D 뷰어 (Jupyter, 선택적)

- **🚀 3D 뷰어 실행 (Jupyter)** 버튼: jupyter_cadquery를 사용한 고급 시각화
- Jupyter 환경에서만 실행 가능

```bash
# Jupyter 환경에서 실행
jupyter notebook
# 또는
jupyter lab

# 노트북에서 다음 코드 실행
%run model_checker_3d.py
```

## 파일 구조

```
3D_Model_GUI/
├── gui_main.py              # GUI 메인 프로그램 (Enhanced)
├── gui_main_v1.py           # 이전 버전 (백업)
├── model_checker_3d.py      # 3D 모델 체커 (Jupyter용)
├── requirements.txt         # 의존성 패키지
├── README.md               # 이 파일
├── example_components.csv  # 예제 파일
├── .gitignore              # Git 제외 파일
└── components.csv          # 생성된 컴포넌트 데이터 (실행 후)
```

## CSV 형식

```csv
name,type,parent,L,W,T,D,H,cx,cy,cz,color,coord_file,coord_has_header
base_plate,box,root,100,100,5,,,0,0,0,lightgray,,true
pillar1,cyl,base_plate,,,,,10,5,10,10,5,steelblue,,true
```

### 컬럼 설명

- `name`: 컴포넌트 이름 (고유해야 함)
- `type`: 타입 (assembly, box, cyl, sphere)
- `parent`: 부모 이름 (root 또는 다른 assembly)
- `L, W, T`: Box 치수 (길이, 너비, 두께)
- `D`: Cylinder/Sphere 직경
- `H`: Cylinder 높이
- `cx, cy, cz`: 중심 좌표 (cz는 바닥면 높이)
- `color`: 색상 (비어있으면 랜덤)
- `coord_file`: 패턴 배치용 좌표 파일
- `coord_has_header`: 좌표 파일에 헤더가 있는지 여부

## 좌표 파일 형식 (패턴)

좌표 파일을 지정하면 해당 좌표들에 동일한 형상을 반복 배치합니다.

```
x,y,z_offset
10,20,0
30,40,0
50,60,5
```

- 콤마, 공백, 탭 구분자 모두 지원
- z_offset은 선택사항 (기본값 0)

## 구현 완료된 기능 ✅

- [x] 3D 미리보기 통합 (GUI 내부에서 직접 보기)
- [x] 드래그 앤 드롭으로 계층 구조 변경
- [x] Undo/Redo 기능
- [x] 키보드 단축키
- [x] 3분할 레이아웃

## 향후 개선 사항

- [ ] 실시간 자동 저장 (Auto-save)
- [ ] 복사/붙여넣기 기능
- [ ] 검색 및 필터링
- [ ] 템플릿 저장/불러오기
- [ ] 더 많은 형상 타입 지원 (Torus, Cone, 사용자 정의 등)
- [ ] 색상 선택기 (Color Picker)
- [ ] 다중 선택 및 일괄 편집
- [ ] Export to STEP/STL

## 라이센스

MIT

## 문의

이슈나 개선 사항은 GitHub Issues에 등록해주세요.
