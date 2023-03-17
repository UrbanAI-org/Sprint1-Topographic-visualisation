# from osgeo import gdal
import matplotlib.pyplot as plt
from geotiff import GeoTiff
import numpy as np
import open3d as o3d
from multiprocessing.pool import ThreadPool
from collections import deque
geo_tiff = GeoTiff('s34_e151_1arc_v3.tif')
# the original crs code
print(geo_tiff.crs_code)
# the current crs code
print(geo_tiff.as_crs)
# the shape of the tiff
print(geo_tiff.tif_shape)
# the bounding box in the as_crs CRS
print(geo_tiff.tif_bBox)
# the bounding box as WGS 84
print(geo_tiff.tif_bBox_wgs_84)
# the bounding box in the as_crs converted coordinates
print(geo_tiff.tif_bBox_converted)
geo_tiff
zarr_array = geo_tiff.read()
# read tiff data
array = np.array(zarr_array)

# visualization the tiff file 
# plt.imshow(array, interpolation='none', cmap='gist_gray')
# plt.show()

# --------------------------------------------
# if we assume that the value in array is the altitude of given position.
# Output visualization for each SKIP point. If SKIP = 1, output every point, if SKIP = 2, output every two points.
SKIP = 1
pool = ThreadPool(processes=40)

# add_array(*args) trans(*args):
# convert np.array() 
# [[1,1,1,1,1,], [1,1,1,1,1,], ...,[1,1,1,1,1,]] 
# => 
# [[0,0,1], [0,1,1], ...., [n, n-1, 1], [n,n,1]]
def add_array(col, rows, array):
    temp = np.empty((rows, 3))
    row = 0
    while row < rows:
        temp[row] = np.array([row, col, array[row]])
        row += SKIP
    return temp

def trans(cols, rows, array):
    queue = deque([])
    col = 0
    while col < cols:
    # for col in range(cols):
        task = pool.apply_async(add_array, (col, rows, array[col]))
        queue.append(task)
        col += SKIP
    print("DONE TASKS", len(queue))
    buf = np.array(queue.popleft().get())
    while len(queue) != 0:
        ele = queue.popleft().get()
        buf = np.concatenate((buf, ele), axis=0)
    return buf


# output 200 * 100 points
buf = trans(200, 100, array)
# output 500 * 100 points
buf2 = trans(500, 500, array)

# convert np array into PointCloud
pcd = o3d.geometry.PointCloud()
pcd2 = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(buf)
pcd2.points = o3d.utility.Vector3dVector(buf2)

print("Generate TriangleMesh ...")
pcd.estimate_normals()
pcd2.estimate_normals()

# transfer pointcloud to mesh surfaces
tr_mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd)

# remove box borders
bbox = pcd.get_axis_aligned_bounding_box()
p_mesh_crop = tr_mesh[0].crop(bbox)
print("Generate TriangleMesh Done.")

# visualization
# o3d.visualization.draw_geometries([p_mesh_crop, pcd, pcd2])
# in open3d we just need do like this to export mesh surfaces 
o3d.io.write_triangle_mesh("test.ply", p_mesh_crop)
