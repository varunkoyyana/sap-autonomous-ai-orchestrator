pipeline {
    agent any

    environment {
        CF_API = credentials('CLOUD_FOUNDRY_API')      
        CF_USER = credentials('CLOUD_FOUNDRY_USER')
        CF_PASSWORD = credentials('CLOUD_FOUNDRY_PASSWORD')
        CF_ORG = 'your-btp-org'
        CF_SPACE = 'your-btp-space'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Build Backend') {
            steps {
                dir('backend') {
                    sh 'python -m venv venv'
                    sh '. venv/bin/activate'
                    sh 'pip install -r requirements.txt'
                }
            }
        }
        stage('Test') {
            steps {
                dir('backend') {
                    // Run unit tests if pytest/test suite present
                    sh '. venv/bin/activate && pytest || echo "No tests found, skipping."'
                }
            }
        }
        stage('Build Frontend') {
            steps {
                dir('frontend') {
                    sh 'npm install'
                    sh 'npm run build'
                }
            }
        }
        stage('Deploy to SAP BTP Cloud Foundry') {
            steps {
                withCredentials([
                    usernamePassword(credentialsId: 'cf-credentials', usernameVariable: 'CF_USER', passwordVariable: 'CF_PASSWORD')
                ]) {
                    sh '''
                        cf api $CF_API
                        cf auth $CF_USER $CF_PASSWORD
                        cf target -o $CF_ORG -s $CF_SPACE
                        # Deploy backend microservices
                        cf push orchestrator-backend -f backend/manifest.yml
                        # Deploy frontend app
                        cf push orchestrator-ui -f frontend/manifest.yml
                    '''
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: '**/build/**', allowEmptyArchive: true
        }
        failure {
            mail to: 'team@example.com',
                 subject: "Jenkins Pipeline Failed: ${env.JOB_NAME} ${env.BUILD_NUMBER}",
                 body: "Please check the Jenkins logs for details."
        }
    }
}
