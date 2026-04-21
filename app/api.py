from fastapi import APIRouter
from app.services import analysis_job
from app.schemas import JobRequest



router = APIRouter()

@router.post("/job/analysis")
def analysis_job_api(request: JobRequest) -> dict[str, str | int]:
    return analysis_job(request)