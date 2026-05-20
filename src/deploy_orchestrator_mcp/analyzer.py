from deploy_orchestrator_mcp.stack_detector import detect_stack


def analyze_file_list(files):
    stack = detect_stack(files)

    return {
        "runtime": stack["runtime"],
        "framework": stack["framework"],
        "has_dockerfile": stack["has_dockerfile"],
        "needs_database": stack["needs_database"],
        "needs_supabase": stack["needs_supabase"],
        "frontend": stack["frontend"],
        "detected_files": sorted(files),
    }
