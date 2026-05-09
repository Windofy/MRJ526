@echo off
REM MRJ526 — Cloud Run Deploy Script
REM Usage: deploy.bat [PROJECT_ID]

SET PROJECT_ID=%1
IF "%PROJECT_ID%"=="" SET PROJECT_ID=mrj-jealousy

SET SERVICE=mrj-jealousy
SET REGION=europe-west1
SET IMAGE=gcr.io/%PROJECT_ID%/%SERVICE%:latest

echo.
echo === MRJ526 Deploy to Cloud Run ===
echo Project:  %PROJECT_ID%
echo Service:  %SERVICE%
echo Region:   %REGION%
echo Image:    %IMAGE%
echo.

REM Build and submit the Docker image
echo [1/3] Building Docker image...
gcloud builds submit --tag %IMAGE% --project %PROJECT_ID%
IF ERRORLEVEL 1 ( echo Build failed! & exit /b 1 )

REM Deploy to Cloud Run
echo [2/3] Deploying to Cloud Run...
gcloud run deploy %SERVICE% ^
  --image %IMAGE% ^
  --platform managed ^
  --region %REGION% ^
  --allow-unauthenticated ^
  --memory 2Gi ^
  --cpu 2 ^
  --timeout 300 ^
  --set-env-vars PYTHONUNBUFFERED=1 ^
  --project %PROJECT_ID%
IF ERRORLEVEL 1 ( echo Deploy failed! & exit /b 1 )

echo [3/3] Getting service URL...
gcloud run services describe %SERVICE% --region %REGION% --project %PROJECT_ID% --format "value(status.url)"

echo.
echo === Deploy complete! ===
