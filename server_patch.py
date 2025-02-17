import json
import time
import logging
import traceback
from pathlib import Path
from aiohttp import web
import nodes
import folder_paths
import threading

class NodeInfoManager:
    """节点信息管理器"""
    def __init__(self):
        self._cache = {}
        self._initialized = False
        self._lock = threading.Lock()
        self._start_time = None
        print("=== 初始化节点信息管理器 ===")
        
        # 启动后台监控线程
        self._monitor_thread = threading.Thread(target=self._monitor_nodes, daemon=True)
        self._monitor_thread.start()

    def _monitor_nodes(self):
        """监控并处理新加载的节点"""
        processed_nodes = set()
        last_total = 0
        
        while True:
            try:
                if not hasattr(nodes, 'NODE_CLASS_MAPPINGS'):
                    time.sleep(0.1)
                    continue
                    
                # 获取新加载的节点
                current_nodes = set(nodes.NODE_CLASS_MAPPINGS.keys())
                new_nodes = current_nodes - processed_nodes
                
                if new_nodes:
                    if self._start_time is None:
                        self._start_time = time.time()
                    
                    # 处理新节点
                    for node_class in new_nodes:
                        self._process_node(node_class, nodes.NODE_CLASS_MAPPINGS[node_class])
                        processed_nodes.add(node_class)
                
                # 当节点数量发生变化时显示进度
                current_total = len(nodes.NODE_CLASS_MAPPINGS)
                if current_total != last_total and current_total > 0:
                    elapsed = time.time() - self._start_time if self._start_time else 0
                    
                    print(f"进度: {current_total}/{current_total} (100.0%)")
                    print(f"  - 已完成节点信息收集 (已加载节点: {current_total})")
                    print(f"  - 总耗时: {elapsed:.1f} 秒")
                    
                    last_total = current_total
                
                # 增加额外的延迟以等待所有节点加载
                if current_total > 0:
                    time.sleep(0.1)
                else:
                    time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"节点监控出错: {str(e)}")
                logging.error(traceback.format_exc())
                time.sleep(1)

    def _process_node(self, node_class, obj_class):
        """处理单个节点信息"""
        try:
            info = {}
            info['input'] = obj_class.INPUT_TYPES()
            info['input_order'] = {key: list(value.keys()) for (key, value) in obj_class.INPUT_TYPES().items()}
            info['output'] = obj_class.RETURN_TYPES
            info['output_is_list'] = obj_class.OUTPUT_IS_LIST if hasattr(obj_class, 'OUTPUT_IS_LIST') else [False] * len(obj_class.RETURN_TYPES)
            info['output_name'] = obj_class.RETURN_NAMES if hasattr(obj_class, 'RETURN_NAMES') else info['output']
            info['name'] = node_class
            info['display_name'] = nodes.NODE_DISPLAY_NAME_MAPPINGS.get(node_class, node_class)
            info['description'] = getattr(obj_class, 'DESCRIPTION', '')
            info['python_module'] = getattr(obj_class, "RELATIVE_PYTHON_MODULE", "nodes")
            info['category'] = getattr(obj_class, 'CATEGORY', 'sd')
            info['output_node'] = hasattr(obj_class, 'OUTPUT_NODE') and obj_class.OUTPUT_NODE

            if hasattr(obj_class, 'OUTPUT_TOOLTIPS'):
                info['output_tooltips'] = obj_class.OUTPUT_TOOLTIPS
            if getattr(obj_class, "DEPRECATED", False):
                info['deprecated'] = True
            if getattr(obj_class, "EXPERIMENTAL", False):
                info['experimental'] = True
            
            with self._lock:
                self._cache[node_class] = info
                
            return True
        except Exception as e:
            logging.error(f"处理节点 {node_class} 时出错: {str(e)}")
            logging.error(traceback.format_exc())
            return False

    def initialize(self):
        """初始化触发函数（实际初始化在后台进行）"""
        pass

    def get_node_info(self, node_class):
        """获取单个节点的信息"""
        return self._cache.get(node_class)

    def get_all_nodes_info(self):
        """获取所有节点的信息"""
        return self._cache

# 创建全局实例
node_info_manager = NodeInfoManager()

def create_node_info():
    """创建节点信息处理函数"""
    def node_info(node_class):
        """获取单个节点的信息"""
        obj_class = nodes.NODE_CLASS_MAPPINGS[node_class]
        info = {}
        info['input'] = obj_class.INPUT_TYPES()
        info['input_order'] = {key: list(value.keys()) for (key, value) in obj_class.INPUT_TYPES().items()}
        info['output'] = obj_class.RETURN_TYPES
        info['output_is_list'] = obj_class.OUTPUT_IS_LIST if hasattr(obj_class, 'OUTPUT_IS_LIST') else [False] * len(obj_class.RETURN_TYPES)
        info['output_name'] = obj_class.RETURN_NAMES if hasattr(obj_class, 'RETURN_NAMES') else info['output']
        info['name'] = node_class
        info['display_name'] = nodes.NODE_DISPLAY_NAME_MAPPINGS[node_class] if node_class in nodes.NODE_DISPLAY_NAME_MAPPINGS.keys() else node_class
        info['description'] = obj_class.DESCRIPTION if hasattr(obj_class,'DESCRIPTION') else ''
        info['python_module'] = getattr(obj_class, "RELATIVE_PYTHON_MODULE", "nodes")
        info['category'] = 'sd'
        
        if hasattr(obj_class, 'OUTPUT_NODE') and obj_class.OUTPUT_NODE == True:
            info['output_node'] = True
        else:
            info['output_node'] = False

        if hasattr(obj_class, 'CATEGORY'):
            info['category'] = obj_class.CATEGORY

        if hasattr(obj_class, 'OUTPUT_TOOLTIPS'):
            info['output_tooltips'] = obj_class.OUTPUT_TOOLTIPS

        if getattr(obj_class, "DEPRECATED", False):
            info['deprecated'] = True
        if getattr(obj_class, "EXPERIMENTAL", False):
            info['experimental'] = True
        return info
    return node_info

def create_patched_routes():
    """创建补丁后的路由处理函数"""
    original_node_info = create_node_info()
    
    async def get_object_info(request):
        """处理 /object_info 路由"""
        if not node_info_manager._initialized:
            # 如果缓存未初始化，使用原始处理函数
            out = {}
            for x in nodes.NODE_CLASS_MAPPINGS:
                try:
                    out[x] = original_node_info(x)
                except Exception:
                    logging.error(f"[ERROR] An error occurred while retrieving information for the '{x}' node.")
                    logging.error(traceback.format_exc())
            return web.json_response(out)
        return web.json_response(node_info_manager.get_all_nodes_info())

    async def get_object_info_node(request):
        """处理 /object_info/{node_class} 路由"""
        node_class = request.match_info.get("node_class", None)
        out = {}
        if node_class is not None and node_class in nodes.NODE_CLASS_MAPPINGS:
            if not node_info_manager._initialized:
                # 如果缓存未初始化，使用原始处理方式
                out[node_class] = original_node_info(node_class)
            else:
                info = node_info_manager.get_node_info(node_class)
                if info:
                    out[node_class] = info
        return web.json_response(out)
        
    return get_object_info, get_object_info_node

def apply_patch(server_instance):
    """应用补丁到服务器实例"""
    try:
        # 初始化节点信息
        node_info_manager.initialize()
        
        # 创建新的路由处理函数
        get_object_info, get_object_info_node = create_patched_routes()
        
        # 获取路由装饰器
        routes = server_instance.routes
        
        # 使用路由装饰器的原始方法添加路由
        if hasattr(routes, 'original_routes'):
            # HotReloadHack 环境
            routes = routes.original_routes
            
        # 使用装饰器语法添加路由
        routes.get("/object_info")(get_object_info)
        routes.get("/object_info/{node_class}")(get_object_info_node)
        
        print("Server 补丁已应用")
        
    except Exception as e:
        logging.error(f"应用补丁时出错: {str(e)}")
        logging.error(traceback.format_exc())
        print("补丁应用失败，将使用原始路由处理")

if __name__ == "__main__":
    patch_server() 