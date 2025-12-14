import cv2
import numpy as np
import os
import matplotlib
# Force Agg backend to prevent GUI thread conflicts
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def apply_ghost_removal(img, dx, dy, amp):
    if amp == 0.0 or (dx == 0 and dy == 0): return img
    rows, cols = img.shape
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    ghost = cv2.warpAffine(img, M, (cols, rows))
    return img - (ghost * amp)

def create_histogram(img):
    if len(img.shape) == 3: img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([img], [0], None, [256], [0, 256])
    h_h, h_w = 100, 256
    hist_img = np.zeros((h_h, h_w, 3), dtype=np.uint8)
    cv2.normalize(hist, hist, 0, h_h, cv2.NORM_MINMAX)
    for i in range(1, 256):
        pt1 = (i - 1, h_h - int(hist[i - 1]))
        pt2 = (i, h_h - int(hist[i]))
        col = (255 - i, i, 100)
        cv2.line(hist_img, pt1, pt2, col, 1)
    return hist_img

def process_frame(signal, bg, gain, mode, ghost_params=None):
    if bg is None or mode == "Raw":
        if len(signal.shape) == 2: return cv2.cvtColor(signal, cv2.COLOR_GRAY2BGR)
        return signal

    S = signal.astype(np.float32)
    B = bg.astype(np.float32)
    
    if S.shape != B.shape: B = cv2.resize(B, (S.shape[1], S.shape[0]))

    # 1. Initial Difference
    diff = S - B

    # --- FLICKER FIX: HIGH PASS FILTER ---
    # We calculate the low-frequency "glow" or "flicker" of the image
    # by blurring the difference heavily.
    # Sigma=30 means "features larger than ~30 pixels".
    # Global flicker affects the whole image (infinity pixels), so this catches it.
    background_drift = cv2.GaussianBlur(diff, (0, 0), sigmaX=30, sigmaY=30)
    
    # Subtract the drift. This centers the data around 0.0 regardless of LED power.
    diff = diff - background_drift
    # -------------------------------------

    # 2. De-Ghosting
    if ghost_params: 
        diff = apply_ghost_removal(diff, *ghost_params)

    # 3. Amplify
    diff_amp = diff * gain
    
    final_bgr = None
    
    if "Abs Diff" in mode:
        final = np.abs(diff_amp)
        final_bgr = cv2.cvtColor(np.clip(final, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        
    elif "Enhanced" in mode:
        # Add back to original background
        final = B + diff_amp
        final_bgr = cv2.cvtColor(np.clip(final, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    
    elif "Colorize" in mode:
        plane_b = np.zeros_like(diff_amp)
        plane_g = np.zeros_like(diff_amp)
        plane_r = np.zeros_like(diff_amp)
        
        # Dimmed background for context
        base = B * 0.4
        plane_r = base.copy()
        plane_g = base.copy()
        plane_b = base.copy()

        # Apply Colors
        plane_r[diff_amp > 0] += diff_amp[diff_amp > 0]
        plane_b[diff_amp < 0] -= diff_amp[diff_amp < 0]
        
        merged = cv2.merge([plane_b, plane_g, plane_r])
        final_bgr = np.clip(merged, 0, 255).astype(np.uint8)
    
    elif "Heatmap" in mode:
        # For heatmap, we want to center the noise at 127 (Gray)
        # Since we removed the drift, the mean is guaranteed to be ~0.0.
        # So we just add 127.
        norm_byte = np.clip(diff_amp + 127, 0, 255).astype(np.uint8)

        cmap = cv2.COLORMAP_JET
        if "Inferno" in mode: cmap = cv2.COLORMAP_INFERNO
        elif "Viridis" in mode: cmap = cv2.COLORMAP_VIRIDIS
        final_bgr = cv2.applyColorMap(norm_byte, cmap)
        
    else:
        final_bgr = cv2.cvtColor(signal.astype(np.uint8), cv2.COLOR_GRAY2BGR)

    return final_bgr

def render_3d_frame(cv_img, step_down=4, elev=30, azim=-60, axis_x=0, mode="Topography"):
    if len(cv_img.shape) == 3: gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    else: gray = cv_img
    h, w = gray.shape
    fig = plt.figure(figsize=(10, 6), dpi=80)
    ax = fig.add_subplot(111, projection='3d')

    if mode == "Stacked Slices":
        col_idx = max(0, min(axis_x, w-1)); roi = gray[:, col_idx:]; rh, rw = roi.shape
        num_slices = 30; slice_step = max(1, rh // num_slices); theta = np.linspace(0, 2*np.pi, 50)
        for y in range(0, rh, slice_step):
            row_data = roi[y, :][::step_down]
            dmin, dmax = row_data.min(), row_data.max()
            norm_row = (row_data - dmin) / (dmax - dmin) if dmax - dmin > 10 else row_data / 255.0
            r = np.arange(len(row_data)); R, Theta = np.meshgrid(r, theta)
            X = R * np.cos(Theta); Y = R * np.sin(Theta); Z = np.full_like(X, rh - y) 
            intensity = np.tile(norm_row, (len(theta), 1))
            colors = plt.cm.jet(intensity); colors[:, :, 3] = np.power(intensity, 3) * 0.9 + 0.1
            ax.plot_surface(X, Y, Z, facecolors=colors, rstride=1, cstride=1, shade=False)
        ax.set_box_aspect((1, 1, 3))
    elif mode == "Revolution":
        col_idx = max(0, min(axis_x, w-1)); start_c = max(0, col_idx-2); end_c = min(w, col_idx+3)
        slice_data = np.mean(gray[:, start_c:end_c], axis=1)[::step_down]
        d_min, d_max = slice_data.min(), slice_data.max()
        norm_data = (slice_data - d_min) / (d_max - d_min) if dmax > d_min else slice_data/255.0
        z = np.arange(len(slice_data)); theta = np.linspace(0, 2*np.pi, 60); Z, Theta = np.meshgrid(z, theta)
        R = 10 + (np.tile(norm_data, (len(theta), 1)) * 15.0)
        X = R * np.cos(Theta); Y = R * np.sin(Theta)
        color_matrix = np.tile(norm_data, (len(theta), 1))
        surf = ax.plot_surface(X, Y, Z, facecolors=plt.cm.inferno(color_matrix), shade=False); ax.set_box_aspect((1, 1, 3))
    else:
        start_col = max(0, min(axis_x, w-1)); roi = gray[:, start_col:]; down = roi[::step_down, ::step_down]
        f_img = down.astype(np.float32); f_bg = cv2.GaussianBlur(f_img, (31, 31), 0); z_data = f_img - f_bg
        dmin, dmax = z_data.min(), z_data.max()
        norm_down = (z_data - dmin) / (d_max - d_min) if dmax > dmin else (z_data - dmin)
        X, Y = np.meshgrid(np.arange(down.shape[1]), np.arange(down.shape[0]))
        surf = ax.plot_surface(X, Y, z_data, facecolors=plt.cm.jet(norm_down), linewidth=0, antialiased=False); ax.set_zlim(-50, 50); ax.set_box_aspect((4, 3, 0.4))

    ax.axis('off'); ax.view_init(elev=elev, azim=azim)
    fig.canvas.draw(); buf = fig.canvas.buffer_rgba()
    data = np.frombuffer(buf, dtype=np.uint8)
    w_can, h_can = fig.canvas.get_width_height(); data = data.reshape((h_can, w_can, 4)); plt.close(fig)
    return cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)

def generate_video(scan_dir, fps=10, render_3d=False, elev=30, azim=-60, axis_x=0, mode_3d="Topography"):
    images = sorted([img for img in os.listdir(scan_dir) if img.endswith(".png") and img.startswith("frame_")])
    if not images: return None
    frame0 = cv2.imread(os.path.join(scan_dir, images[0]))
    if render_3d:
        temp = render_3d_frame(frame0, step_down=4, elev=elev, azim=azim, axis_x=axis_x, mode=mode_3d)
        h, w, _ = temp.shape
    else: h, w, _ = frame0.shape
    out_path = os.path.join(scan_dir, "output_3d.avi" if render_3d else "output_2d.avi")
    video = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'MJPG'), fps, (w, h))
    count = 0; total = len(images)
    print(f"Generating Video ({total} frames)...")
    for image in images:
        count += 1
        if count % 10 == 0: print(f"Encoding {count}/{total}...")
        frame = cv2.imread(os.path.join(scan_dir, image))
        if render_3d: frame = render_3d_frame(frame, step_down=4, elev=elev, azim=azim, axis_x=axis_x, mode=mode_3d)
        video.write(frame)
    video.release()
    return out_path

def save_image(img, folder, filename):
    if not os.path.exists(folder): os.makedirs(folder)
    cv2.imwrite(os.path.join(folder, filename), img)
