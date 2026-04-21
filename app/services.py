from app.schemas import JobRequest

def analysis_job(request: JobRequest) -> dict[str, str | int]:
    jd = request.job_text

    # 去除空字符
    jd = jd.strip()  # 去除字符串开头和结尾的空白字符

    # 非空校验
    if not jd:
        return{
            "error":"岗位描述不能为空",
            "msg":"请提供有效的岗位描述"
        }


    return{
        "original_jd":jd,
        "length":len(jd),
        "msg":"已收到岗位描述"
    }