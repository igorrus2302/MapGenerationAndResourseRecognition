from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Просмотр геологической карты</title>
  <style>
    :root {
      --navy: #102a43;
      --blue: #1677a8;
      --cyan: #2bb3d6;
      --teal: #168c86;
      --orange: #e95e2a;
      --paper: #f6f8fb;
      --line: #d8e0e8;
      --muted: #627d98;
      --text: #243b53;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body {
      color: var(--text);
      background: var(--paper);
      font: 14px/1.45 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }
    header {
      height: 70px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 0 26px;
      color: white;
      background: linear-gradient(120deg, #102a43, #164b6b 70%, #1677a8);
      box-shadow: 0 4px 18px rgba(16, 42, 67, .22);
    }
    .brand { display: flex; align-items: center; gap: 13px; min-width: 0; }
    .brand-mark {
      width: 40px; height: 40px; border-radius: 11px;
      background: linear-gradient(145deg, #36c2df, #168c86);
      display: grid; place-items: center; font-weight: 800; font-size: 18px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.28);
    }
    .brand h1 { margin: 0; font-size: 18px; line-height: 1.2; }
    .brand p { margin: 3px 0 0; color: #cfe5f1; font-size: 12px; }
    .header-stats { display: flex; gap: 8px; flex-wrap: wrap; justify-content: end; }
    .header-stats span {
      padding: 6px 10px; border: 1px solid rgba(255,255,255,.16);
      border-radius: 999px; color: #e5f4fb; background: rgba(255,255,255,.08);
      font-size: 12px; white-space: nowrap;
    }
    .layout { height: calc(100% - 70px); display: grid; grid-template-columns: 300px 1fr; }
    aside {
      overflow: auto;
      padding: 20px 18px 28px;
      background: white;
      border-right: 1px solid var(--line);
    }
    .control-group { margin-bottom: 20px; }
    .control-group h2 {
      margin: 0 0 9px; color: var(--navy); font-size: 12px;
      letter-spacing: .07em; text-transform: uppercase;
    }
    label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    select, button {
      width: 100%; min-height: 38px; border: 1px solid var(--line); border-radius: 9px;
      background: white; color: var(--text); padding: 7px 10px; font: inherit;
    }
    button { cursor: pointer; font-weight: 650; transition: .15s ease; }
    button:hover { border-color: var(--blue); color: var(--blue); }
    .button-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    input[type="range"] { width: 100%; accent-color: var(--blue); }
    .range-line { display: flex; justify-content: space-between; align-items: center; margin-top: 2px; }
    .value-badge {
      color: var(--blue); background: #eaf5fa; border-radius: 7px;
      padding: 3px 7px; font-size: 12px; font-weight: 700;
    }
    .legend-list { display: grid; gap: 7px; }
    .legend-item {
      display: grid; grid-template-columns: 18px 1fr auto; gap: 8px; align-items: center;
      padding: 7px 8px; border: 1px solid #e8edf2; border-radius: 9px;
      cursor: pointer; user-select: none;
    }
    .legend-item:hover { background: #f7fafc; }
    .swatch { width: 16px; height: 16px; border-radius: 5px; box-shadow: inset 0 0 0 1px rgba(0,0,0,.13); }
    .legend-item input { margin: 0; }
    .switch-line { display: flex; align-items: center; gap: 9px; color: var(--text); font-size: 13px; }
    .switch-line input { accent-color: var(--orange); }
    .info-card {
      min-height: 118px; padding: 12px; border-radius: 11px;
      background: linear-gradient(145deg, #f7fafc, #eef5f8); border: 1px solid var(--line);
      color: var(--muted); font-size: 12px;
    }
    .info-card strong { display: block; color: var(--navy); margin-bottom: 5px; font-size: 13px; }
    .info-grid { display: grid; grid-template-columns: auto 1fr; gap: 3px 8px; }
    .info-grid b { color: var(--text); font-weight: 600; text-align: right; }
    main { min-width: 0; min-height: 0; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
    .viewer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 15px; }
    .viewer-toolbar h2 { margin: 0; color: var(--navy); font-size: 16px; }
    .status-pill {
      padding: 5px 9px; border-radius: 999px; color: #11665f; background: #e9f6f4;
      border: 1px solid #bce4df; font-size: 12px; font-weight: 650;
    }
    .canvas-shell {
      position: relative; flex: 1; min-height: 0; overflow: hidden;
      border: 1px solid var(--line); border-radius: 15px;
      background: white; box-shadow: 0 10px 34px rgba(16, 42, 67, .08);
    }
    canvas { width: 100%; height: 100%; display: block; cursor: crosshair; }
    .canvas-hint {
      position: absolute; right: 12px; bottom: 12px; max-width: 360px;
      padding: 7px 10px; border-radius: 8px; color: #536b80;
      background: rgba(255,255,255,.91); border: 1px solid rgba(203,213,225,.9);
      font-size: 11px; pointer-events: none; backdrop-filter: blur(4px);
    }
    .hidden { display: none !important; }
    @media (max-width: 860px) {
      body { overflow: auto; }
      header { height: auto; min-height: 70px; padding: 14px 18px; align-items: flex-start; }
      .header-stats { display: none; }
      .layout { height: auto; grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      main { height: 70vh; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-mark">3D</div>
      <div>
        <h1>Геологическая карта</h1>
        <p>Минимальный генератор истинной модели</p>
      </div>
    </div>
    <div class="header-stats" id="headerStats"></div>
  </header>

  <div class="layout">
    <aside>
      <div class="control-group">
        <h2>Режим просмотра</h2>
        <select id="modeSelect">
          <option value="3d">3D-блок</option>
          <option value="horizontal">Горизонтальный срез</option>
          <option value="vertical-x">Вертикальный разрез по X</option>
          <option value="vertical-y">Вертикальный разрез по Y</option>
        </select>
      </div>

      <div class="control-group hidden" id="depthControls">
        <h2>Глубина среза</h2>
        <input id="depthSlider" type="range" min="0" step="1" value="5">
        <div class="range-line"><span>Глубина</span><span class="value-badge" id="depthValue"></span></div>
      </div>

      <div class="control-group hidden" id="sliceControls">
        <h2>Положение разреза</h2>
        <input id="sliceSlider" type="range" min="0" step="1" value="200">
        <div class="range-line"><span id="sliceAxis">Координата</span><span class="value-badge" id="sliceValue"></span></div>
      </div>

      <div class="control-group" id="view3dControls">
        <h2>Управление 3D</h2>
        <div class="button-row">
          <button id="rotateLeft">↺ Повернуть</button>
          <button id="rotateRight">Повернуть ↻</button>
        </div>
        <button id="resetView" style="margin-top:8px">Сбросить ракурс</button>
      </div>

      <div class="control-group">
        <h2>Породы</h2>
        <div class="legend-list" id="rockLegend"></div>
      </div>

      <div class="control-group">
        <h2>Месторождения</h2>
        <label class="switch-line"><input id="depositToggle" type="checkbox" checked> Показывать минерализацию</label>
      </div>

      <div class="control-group">
        <h2>Выбранная точка</h2>
        <div class="info-card" id="cellInfo">
          <strong>Нет выбранной точки</strong>
          Нажмите на горизонтальный или вертикальный срез, чтобы увидеть данные ячейки.
        </div>
      </div>

      <button id="downloadJson">Скачать map.json</button>
    </aside>

    <main>
      <div class="viewer-toolbar">
        <h2 id="viewTitle">Трёхмерная блочная модель</h2>
        <span class="status-pill">seed <span id="seedValue"></span></span>
      </div>
      <div class="canvas-shell" id="canvasShell">
        <canvas id="mapCanvas"></canvas>
        <div class="canvas-hint" id="canvasHint">Перетаскивайте мышью для вращения, колесом меняйте масштаб.</div>
      </div>
    </main>
  </div>

  <script>
    const MAP_DATA = __MAP_DATA__;

    const canvas = document.getElementById('mapCanvas');
    const ctx = canvas.getContext('2d');
    const shell = document.getElementById('canvasShell');
    const modeSelect = document.getElementById('modeSelect');
    const depthSlider = document.getElementById('depthSlider');
    const depthValue = document.getElementById('depthValue');
    const sliceSlider = document.getElementById('sliceSlider');
    const sliceValue = document.getElementById('sliceValue');
    const sliceAxis = document.getElementById('sliceAxis');
    const depositToggle = document.getElementById('depositToggle');
    const viewTitle = document.getElementById('viewTitle');
    const canvasHint = document.getElementById('canvasHint');
    const cellInfo = document.getElementById('cellInfo');
    const dims = MAP_DATA.dimensions;
    const rockById = Object.fromEntries(MAP_DATA.rocks.map(rock => [rock.id, rock]));
    const depositById = Object.fromEntries(MAP_DATA.deposits.map(deposit => [deposit.id, deposit]));
    const cells = MAP_DATA.cells;
    const presentRockIds = new Set(
      cells.flatMap(cell => cell.intervals.map(interval => interval.rock_id))
    );
    const presentRocks = MAP_DATA.rocks.filter(rock => presentRockIds.has(rock.id));

    const state = {
      mode: '3d',
      depthM: Math.min(5, dims.depth_m - 1),
      slicePositionM: Math.floor(dims.width_m / 2),
      angle: -Math.PI / 4,
      zoom: 1,
      showDeposit: true,
      visibleRocks: new Set(presentRocks.map(rock => rock.id)),
      hitMap: null,
      dragging: false,
      dragX: 0
    };

    document.getElementById('seedValue').textContent = MAP_DATA.seed;
    document.getElementById('headerStats').innerHTML = [
      `${dims.width_m} × ${dims.height_m} м`,
      `глубина ${dims.depth_m} м`,
      `${MAP_DATA.statistics.cell_count} ячеек`,
      `${MAP_DATA.statistics.mineralized_cell_count} минерализованных`
    ].map(text => `<span>${text}</span>`).join('');

    function cellAt(x, y) {
      if (x < 0 || y < 0 || x >= dims.width_cells || y >= dims.height_cells) return null;
      return cells[y * dims.width_cells + x];
    }

    function intervalAt(cell, depthM) {
      if (!cell) return null;
      return cell.intervals.find(interval => depthM >= interval.from_depth_m && depthM < interval.to_depth_m)
        || cell.intervals[cell.intervals.length - 1];
    }

    function mineralizationAt(cell, depthM) {
      if (!cell) return null;
      const matches = cell.mineralization.filter(
        item => depthM >= item.from_depth_m && depthM <= item.to_depth_m
      );
      return matches.reduce(
        (best, item) => !best || item.maximum_concentration_percent > best.maximum_concentration_percent
          ? item : best,
        null
      );
    }

    function depositFor(item) {
      return item ? depositById[item.deposit_id] : null;
    }

    function depositStrength(item) {
      const deposit = depositFor(item);
      return deposit ? Math.min(1, item.maximum_concentration_percent / deposit.max_concentration_percent) : 0;
    }

    function formatConcentration(value) {
      if (value < 0.01) return value.toFixed(4);
      if (value < 1) return value.toFixed(3);
      return value.toFixed(2);
    }

    function hexToRgb(hex) {
      const value = hex.replace('#', '');
      return {
        r: parseInt(value.slice(0, 2), 16),
        g: parseInt(value.slice(2, 4), 16),
        b: parseInt(value.slice(4, 6), 16)
      };
    }

    function rgba(hex, alpha = 1, factor = 1) {
      const {r, g, b} = hexToRgb(hex);
      const clamp = value => Math.max(0, Math.min(255, Math.round(value * factor)));
      return `rgba(${clamp(r)},${clamp(g)},${clamp(b)},${alpha})`;
    }

    function resizeCanvas() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const rect = shell.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      requestRender();
    }

    function canvasSize() {
      return { width: canvas.clientWidth, height: canvas.clientHeight };
    }

    let renderRequested = false;
    function requestRender() {
      if (renderRequested) return;
      renderRequested = true;
      requestAnimationFrame(() => {
        renderRequested = false;
        render();
      });
    }

    function clearCanvas() {
      const {width, height} = canvasSize();
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, '#fbfdff');
      gradient.addColorStop(1, '#eef3f7');
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    }

    function render() {
      clearCanvas();
      if (state.mode === '3d') render3D();
      else if (state.mode === 'horizontal') renderHorizontal();
      else renderVertical(state.mode === 'vertical-x' ? 'x' : 'y');
    }

    function drawPolygon(points, fill, stroke = null, width = 0.45) {
      if (!points.length) return;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let index = 1; index < points.length; index++) ctx.lineTo(points[index].x, points[index].y);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.stroke();
      }
    }

    function projectionFor3D(width, height) {
      const centerX = dims.width_cells / 2;
      const centerY = dims.height_cells / 2;
      const depthSteps = dims.depth_m / dims.depth_step_m;
      const cos = Math.cos(state.angle);
      const sin = Math.sin(state.angle);
      function raw(x, y, z) {
        const dx = x - centerX;
        const dy = y - centerY;
        const rx = dx * cos - dy * sin;
        const ry = dx * sin + dy * cos;
        return {x: rx, y: ry * 0.46 + z * 0.72, depth: ry + z * 0.025};
      }
      const corners = [];
      for (const x of [0, dims.width_cells]) {
        for (const y of [0, dims.height_cells]) {
          for (const z of [0, depthSteps]) corners.push(raw(x, y, z));
        }
      }
      const minX = Math.min(...corners.map(point => point.x));
      const maxX = Math.max(...corners.map(point => point.x));
      const minY = Math.min(...corners.map(point => point.y));
      const maxY = Math.max(...corners.map(point => point.y));
      const scale = Math.min((width - 70) / (maxX - minX), (height - 80) / (maxY - minY)) * state.zoom;
      const offsetX = width / 2 - ((minX + maxX) / 2) * scale;
      const offsetY = height / 2 - ((minY + maxY) / 2) * scale;
      return {
        raw,
        point(x, y, z) {
          const projected = raw(x, y, z);
          return {x: offsetX + projected.x * scale, y: offsetY + projected.y * scale, depth: projected.depth};
        },
        sin,
        cos
      };
    }

    function render3D() {
      const {width, height} = canvasSize();
      const projection = projectionFor3D(width, height);
      const baseShapes = [];

      for (let y = 0; y < dims.height_cells; y++) {
        for (let x = 0; x < dims.width_cells; x++) {
          const cell = cellAt(x, y);
          const rock = rockById[cell.intervals[0].rock_id];
          if (!state.visibleRocks.has(rock.id)) continue;
          const points = [
            projection.point(x, y, 0), projection.point(x + 1, y, 0),
            projection.point(x + 1, y + 1, 0), projection.point(x, y + 1, 0)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, 1.05),
            stroke: 'rgba(20,48,70,.11)'
          });
        }
      }

      const nearX = projection.sin >= 0 ? dims.width_cells : 0;
      const cellX = nearX === 0 ? 0 : dims.width_cells - 1;
      for (let y = 0; y < dims.height_cells; y++) {
        const cell = cellAt(cellX, y);
        for (const interval of cell.intervals) {
          if (!state.visibleRocks.has(interval.rock_id)) continue;
          const rock = rockById[interval.rock_id];
          const z1 = interval.from_depth_m / dims.depth_step_m;
          const z2 = interval.to_depth_m / dims.depth_step_m;
          const points = [
            projection.point(nearX, y, z1), projection.point(nearX, y + 1, z1),
            projection.point(nearX, y + 1, z2), projection.point(nearX, y, z2)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, 0.84),
            stroke: 'rgba(20,48,70,.13)'
          });
        }
      }

      const nearY = projection.cos >= 0 ? dims.height_cells : 0;
      const cellY = nearY === 0 ? 0 : dims.height_cells - 1;
      for (let x = 0; x < dims.width_cells; x++) {
        const cell = cellAt(x, cellY);
        for (const interval of cell.intervals) {
          if (!state.visibleRocks.has(interval.rock_id)) continue;
          const rock = rockById[interval.rock_id];
          const z1 = interval.from_depth_m / dims.depth_step_m;
          const z2 = interval.to_depth_m / dims.depth_step_m;
          const points = [
            projection.point(x, nearY, z1), projection.point(x + 1, nearY, z1),
            projection.point(x + 1, nearY, z2), projection.point(x, nearY, z2)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, 0.72),
            stroke: 'rgba(20,48,70,.14)'
          });
        }
      }

      baseShapes.sort((a, b) => a.depth - b.depth);
      for (const shape of baseShapes) drawPolygon(shape.points, shape.fill, shape.stroke);

      if (state.showDeposit) {
        const depositShapes = [];
        for (const cell of cells) {
          if (!cell.mineralization.length) continue;
          const item = cell.mineralization.reduce(
            (best, current) => current.maximum_concentration_percent > best.maximum_concentration_percent
              ? current : best
          );
          const deposit = depositFor(item);
          const x = cell.x_index;
          const y = cell.y_index;
          const z1 = item.from_depth_m / dims.depth_step_m;
          const z2 = item.to_depth_m / dims.depth_step_m;
          const xFace = projection.sin >= 0 ? x + 1 : x;
          const yFace = projection.cos >= 0 ? y + 1 : y;
          const alpha = 0.30 + 0.34 * depositStrength(item);
          const fill = rgba(deposit.color, alpha, 1.08);
          const top = [
            projection.point(x, y, z1), projection.point(x + 1, y, z1),
            projection.point(x + 1, y + 1, z1), projection.point(x, y + 1, z1)
          ];
          const sideX = [
            projection.point(xFace, y, z1), projection.point(xFace, y + 1, z1),
            projection.point(xFace, y + 1, z2), projection.point(xFace, y, z2)
          ];
          const sideY = [
            projection.point(x, yFace, z1), projection.point(x + 1, yFace, z1),
            projection.point(x + 1, yFace, z2), projection.point(x, yFace, z2)
          ];
          for (const points of [top, sideX, sideY]) {
            depositShapes.push({
              points,
              depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
              fill
            });
          }
        }
        depositShapes.sort((a, b) => a.depth - b.depth);
        for (const shape of depositShapes) {
          drawPolygon(shape.points, shape.fill, 'rgba(146,45,15,.22)', 0.5);
        }
      }

      ctx.fillStyle = 'rgba(16,42,67,.76)';
      ctx.font = '600 12px system-ui, sans-serif';
      ctx.fillText('Поверхность', 18, 25);
      ctx.fillStyle = 'rgba(98,125,152,.9)';
      ctx.font = '11px system-ui, sans-serif';
      ctx.fillText('Цветные боковые грани показывают геологические интервалы', 18, 43);
      state.hitMap = null;
    }

    function gridGeometry(columns, rows) {
      const {width, height} = canvasSize();
      const padding = {left: 52, right: 24, top: 42, bottom: 48};
      const cellSize = Math.min(
        (width - padding.left - padding.right) / columns,
        (height - padding.top - padding.bottom) / rows
      );
      const gridWidth = cellSize * columns;
      const gridHeight = cellSize * rows;
      const left = padding.left + Math.max(0, (width - padding.left - padding.right - gridWidth) / 2);
      const top = padding.top + Math.max(0, (height - padding.top - padding.bottom - gridHeight) / 2);
      return {left, top, cellSize, gridWidth, gridHeight, columns, rows};
    }

    function renderHorizontal() {
      const depthM = state.depthM;
      const geometry = gridGeometry(dims.width_cells, dims.height_cells);
      for (let y = 0; y < dims.height_cells; y++) {
        for (let x = 0; x < dims.width_cells; x++) {
          const cell = cellAt(x, y);
          const interval = intervalAt(cell, depthM);
          const rock = rockById[interval.rock_id];
          const sx = geometry.left + x * geometry.cellSize;
          const sy = geometry.top + y * geometry.cellSize;
          ctx.fillStyle = state.visibleRocks.has(rock.id) ? rock.color : '#e5eaf0';
          ctx.fillRect(sx, sy, geometry.cellSize + .3, geometry.cellSize + .3);
          const mineral = state.showDeposit ? mineralizationAt(cell, depthM) : null;
          if (mineral) {
            const alpha = 0.25 + 0.65 * depositStrength(mineral);
            ctx.fillStyle = rgba(depositFor(mineral).color, alpha);
            ctx.fillRect(sx, sy, geometry.cellSize + .3, geometry.cellSize + .3);
          }
        }
      }
      drawGridFrame(geometry, `Горизонтальный срез на глубине ${Math.round(depthM)} м`);
      state.hitMap = {type: 'horizontal', geometry, depthM};
    }

    function renderVertical(axis) {
      const columns = axis === 'x' ? dims.height_cells : dims.width_cells;
      const maximumIndex = axis === 'x' ? dims.width_cells - 1 : dims.height_cells - 1;
      const sliceIndex = Math.min(
        maximumIndex,
        Math.floor(state.slicePositionM / dims.cell_size_m)
      );
      const geometry = gridGeometry(columns, dims.depth_cells);
      for (let horizontal = 0; horizontal < columns; horizontal++) {
        const x = axis === 'x' ? sliceIndex : horizontal;
        const y = axis === 'x' ? horizontal : sliceIndex;
        const cell = cellAt(x, y);
        for (let z = 0; z < dims.depth_cells; z++) {
          const depthM = (z + 0.5) * dims.depth_step_m;
          const interval = intervalAt(cell, depthM);
          const rock = rockById[interval.rock_id];
          const sx = geometry.left + horizontal * geometry.cellSize;
          const sy = geometry.top + z * geometry.cellSize;
          ctx.fillStyle = state.visibleRocks.has(rock.id) ? rock.color : '#e5eaf0';
          ctx.fillRect(sx, sy, geometry.cellSize + .3, geometry.cellSize + .3);
          const mineral = state.showDeposit ? mineralizationAt(cell, depthM) : null;
          if (mineral) {
            const alpha = 0.25 + 0.65 * depositStrength(mineral);
            ctx.fillStyle = rgba(depositFor(mineral).color, alpha);
            ctx.fillRect(sx, sy, geometry.cellSize + .3, geometry.cellSize + .3);
          }
        }
      }
      const coordinate = state.slicePositionM;
      drawGridFrame(geometry, `Вертикальный разрез: ${axis.toUpperCase()} = ${coordinate} м`);
      state.hitMap = {type: `vertical-${axis}`, geometry, axis, sliceIndex};
    }

    function drawGridFrame(geometry, title) {
      ctx.strokeStyle = 'rgba(16,42,67,.28)';
      ctx.lineWidth = 1;
      ctx.strokeRect(geometry.left, geometry.top, geometry.gridWidth, geometry.gridHeight);
      if (geometry.cellSize >= 7) {
        ctx.strokeStyle = 'rgba(255,255,255,.24)';
        ctx.lineWidth = .5;
        for (let x = 1; x < geometry.columns; x++) {
          const sx = geometry.left + x * geometry.cellSize;
          ctx.beginPath(); ctx.moveTo(sx, geometry.top); ctx.lineTo(sx, geometry.top + geometry.gridHeight); ctx.stroke();
        }
        for (let y = 1; y < geometry.rows; y++) {
          const sy = geometry.top + y * geometry.cellSize;
          ctx.beginPath(); ctx.moveTo(geometry.left, sy); ctx.lineTo(geometry.left + geometry.gridWidth, sy); ctx.stroke();
        }
      }
      ctx.fillStyle = '#102a43';
      ctx.font = '600 13px system-ui, sans-serif';
      ctx.fillText(title, geometry.left, geometry.top - 15);
      ctx.fillStyle = '#627d98';
      ctx.font = '11px system-ui, sans-serif';
      ctx.fillText('0 м', geometry.left - 2, geometry.top + geometry.gridHeight + 22);
      ctx.textAlign = 'right';
      ctx.fillText(`${geometry.columns * dims.cell_size_m} м`, geometry.left + geometry.gridWidth, geometry.top + geometry.gridHeight + 22);
      ctx.textAlign = 'left';
    }

    function updateControls() {
      const is3D = state.mode === '3d';
      const isHorizontal = state.mode === 'horizontal';
      const isVertical = state.mode.startsWith('vertical');
      document.getElementById('view3dControls').classList.toggle('hidden', !is3D);
      document.getElementById('depthControls').classList.toggle('hidden', !isHorizontal);
      document.getElementById('sliceControls').classList.toggle('hidden', !isVertical);
      depthSlider.max = String(dims.depth_m - 1);
      depthSlider.value = String(state.depthM);
      depthValue.textContent = `${state.depthM} м`;
      if (isVertical) {
        const axis = state.mode === 'vertical-x' ? 'X' : 'Y';
        const maximum = (axis === 'X' ? dims.width_m : dims.height_m) - 1;
        state.slicePositionM = Math.min(state.slicePositionM, maximum);
        sliceSlider.max = String(maximum);
        sliceSlider.value = String(state.slicePositionM);
        sliceAxis.textContent = `Координата ${axis}`;
        sliceValue.textContent = `${state.slicePositionM} м`;
      }
      const titles = {
        '3d': 'Трёхмерная блочная модель',
        'horizontal': 'Горизонтальный срез',
        'vertical-x': 'Вертикальный разрез по X',
        'vertical-y': 'Вертикальный разрез по Y'
      };
      viewTitle.textContent = titles[state.mode];
      canvasHint.textContent = is3D
        ? 'Перетаскивайте мышью для вращения, колесом меняйте масштаб.'
        : 'Нажмите на ячейку, чтобы увидеть породу, свойства и концентрацию.';
      canvas.style.cursor = is3D ? 'grab' : 'crosshair';
      requestRender();
    }

    function showCellInfo(cell, depthM) {
      const interval = intervalAt(cell, depthM);
      const rock = rockById[interval.rock_id];
      const mineral = mineralizationAt(cell, depthM);
      const deposit = depositFor(mineral);
      const title = mineral ? deposit.name : rock.name;
      const mineralRows = mineral
        ? `
          <span>Ископаемое</span><b>${mineral.mineral}</b>
          <span>Концентрация</span><b>${formatConcentration(mineral.average_concentration_percent)} %</b>
          <span>Порода-носитель</span><b>${rock.name}</b>`
        : `
          <span>Ископаемое</span><b>нет</b>
          <span>Порода</span><b>${rock.name}</b>`;
      cellInfo.innerHTML = `
        <strong>${title}</strong>
        <div class="info-grid">
          <span>Ячейка</span><b>(${cell.x_index}, ${cell.y_index})</b>
          <span>Координаты</span><b>${cell.x_m}-${cell.x_m + dims.cell_size_m} / ${cell.y_m}-${cell.y_m + dims.cell_size_m} м</b>
          <span>Глубина</span><b>${Math.round(depthM)} м</b>
          <span>Интервал</span><b>${interval.from_depth_m}-${interval.to_depth_m} м</b>
          ${mineralRows}
          <span>Плотность</span><b>${interval.properties.density_g_cm3} г/см³</b>
          <span>Пористость</span><b>${interval.properties.porosity_percent} %</b>
        </div>`;
    }

    function hitTest(event) {
      if (!state.hitMap) return;
      const rect = canvas.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      const {geometry} = state.hitMap;
      const column = Math.floor((mouseX - geometry.left) / geometry.cellSize);
      const row = Math.floor((mouseY - geometry.top) / geometry.cellSize);
      if (column < 0 || row < 0 || column >= geometry.columns || row >= geometry.rows) return;
      if (state.hitMap.type === 'horizontal') {
        showCellInfo(cellAt(column, row), state.hitMap.depthM);
        return;
      }
      const depthM = Math.min(
        dims.depth_m - 1,
        Math.floor((mouseY - geometry.top) / geometry.gridHeight * dims.depth_m)
      );
      const cell = state.hitMap.axis === 'x'
        ? cellAt(state.hitMap.sliceIndex, column)
        : cellAt(column, state.hitMap.sliceIndex);
      showCellInfo(cell, depthM);
    }

    function buildLegend() {
      const legend = document.getElementById('rockLegend');
      legend.innerHTML = '';
      for (const rock of presentRocks) {
        const item = document.createElement('label');
        item.className = 'legend-item';
        item.innerHTML = `<span class="swatch" style="background:${rock.color}"></span><span>${rock.name}</span><input type="checkbox" checked>`;
        const input = item.querySelector('input');
        input.addEventListener('change', () => {
          if (input.checked) state.visibleRocks.add(rock.id);
          else state.visibleRocks.delete(rock.id);
          requestRender();
        });
        legend.appendChild(item);
      }
    }

    modeSelect.addEventListener('change', () => {
      state.mode = modeSelect.value;
      state.hitMap = null;
      updateControls();
    });
    depthSlider.addEventListener('input', () => {
      state.depthM = Number(depthSlider.value);
      updateControls();
    });
    sliceSlider.addEventListener('input', () => {
      state.slicePositionM = Number(sliceSlider.value);
      updateControls();
    });
    depositToggle.addEventListener('change', () => {
      state.showDeposit = depositToggle.checked;
      requestRender();
    });
    document.getElementById('rotateLeft').addEventListener('click', () => {
      state.angle -= Math.PI / 8;
      requestRender();
    });
    document.getElementById('rotateRight').addEventListener('click', () => {
      state.angle += Math.PI / 8;
      requestRender();
    });
    document.getElementById('resetView').addEventListener('click', () => {
      state.angle = -Math.PI / 4;
      state.zoom = 1;
      requestRender();
    });
    document.getElementById('downloadJson').addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(MAP_DATA, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'map.json';
      link.click();
      URL.revokeObjectURL(url);
    });

    canvas.addEventListener('click', event => {
      if (state.mode !== '3d') hitTest(event);
    });
    canvas.addEventListener('pointerdown', event => {
      if (state.mode !== '3d') return;
      state.dragging = true;
      state.dragX = event.clientX;
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = 'grabbing';
    });
    canvas.addEventListener('pointermove', event => {
      if (!state.dragging || state.mode !== '3d') return;
      state.angle += (event.clientX - state.dragX) * 0.012;
      state.dragX = event.clientX;
      requestRender();
    });
    canvas.addEventListener('pointerup', event => {
      if (!state.dragging) return;
      state.dragging = false;
      canvas.releasePointerCapture(event.pointerId);
      canvas.style.cursor = 'grab';
    });
    canvas.addEventListener('wheel', event => {
      if (state.mode !== '3d') return;
      event.preventDefault();
      state.zoom = Math.max(.55, Math.min(1.8, state.zoom * (event.deltaY > 0 ? .92 : 1.08)));
      requestRender();
    }, {passive: false});

    buildLegend();
    new ResizeObserver(resizeCanvas).observe(shell);
    updateControls();
  </script>
</body>
</html>
'''


def build_viewer(data: dict[str, Any], path: str | Path) -> Path:
    """Create a standalone offline HTML viewer with the map embedded in it."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__MAP_DATA__", embedded)
    output_path.write_text(html, encoding="utf-8")
    return output_path
