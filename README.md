# 3D Model Checker GUI

3D Assembly 구조를 GUI로 편집하고 CSV로 저장한 뒤 3D로 시각화하는 통합 도구입니다.

## 주요 기능

- **GUI 기반 Assembly 편집**: CSV 파일을 직접 편집하는 대신 GUI로 편리하게 작성
- **계층 구조 관리**: Assembly와 Part를 트리 구조로 관리
- **다양한 형상 지원**: Box, Cylinder, Sphere
- **패턴 배치**: 좌표 파일을 이용한 반복 패턴 지원
- **CSV 저장/불러오기**: 기존 CSV와 호환
- **3D 뷰어 통합**: CadQuery + jupyter_cadquery로 3D 시각화

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

### 2. 컴포넌트 추가

1. **이름** 입력
2. **타입** 선택 (Assembly, Box, Cylinder, Sphere)
3. **부모** 선택 (계층 구조)
4. **형상 파라미터** 입력
   - Box: L (길이), W (너비), T (두께)
   - Cylinder: D (직경), H (높이)
   - Sphere: D (직경)
5. **위치 파라미터** 입력
   - cx, cy: X, Y 좌표
   - cz: Z 바닥면 높이
6. **(선택) 색상** 입력
7. **(선택) 좌표 파일** 선택 (패턴 배치용)
8. **추가** 버튼 클릭

### 3. CSV 저장

- 하단의 **CSV 저장** 버튼을 클릭하여 `components.csv` 파일로 저장

### 4. 3D 뷰어 실행

- **3D 뷰어 실행** 버튼을 클릭하면 자동으로 CSV를 저장하고 3D 뷰어를 실행합니다
- 3D 뷰어는 Jupyter 환경에서 실행해야 합니다

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
├── gui_main.py              # GUI 메인 프로그램
├── model_checker_3d.py      # 3D 모델 체커 (기존 코드)
├── requirements.txt         # 의존성 패키지
├── README.md               # 이 파일
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

## 향후 개선 사항

- [ ] 3D 미리보기 통합 (GUI 내부에서 직접 보기)
- [ ] 드래그 앤 드롭으로 계층 구조 변경
- [ ] Undo/Redo 기능
- [ ] 템플릿 저장/불러오기
- [ ] 더 많은 형상 타입 지원

## 라이센스

MIT

## 문의

이슈나 개선 사항은 GitHub Issues에 등록해주세요.
