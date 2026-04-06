---
name: 3D Surface 시각화 (OpenGL)
description: OpenGL 3D 표면 렌더링, 컬러바, Z-스케일 슬라이더, 다항식 분해
version: 1.0
---
# SKILL 04 — 3D Surface 시각화
## 핵심 요소
- **GLViewWidget**: pyqtgraph.opengl 기반 3D 렌더링
- **Surface Mesh**: GLMeshItem + MeshData + griddata 보간
- **ColorBarWidget**: QPainter 커스텀 페인트 (QLinearGradient)
- **Z-axis 스케일**: QSlider → 0.1x ~ 5.0x 실시간 리렌더
- **Surface Fit Decomposition**: scipy.optimize.curve_fit
  - Original (원본), Tilt (1차 평면), Curve (2차 곡면), Residual (잔차)
- **Z=0 기준면**: 반투명 GLMeshItem 평면
## 관련 파일
`charts/surface3d.py`
