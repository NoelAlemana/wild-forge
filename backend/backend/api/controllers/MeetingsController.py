import os
import requests
import datetime
import jwt
from rest_framework import viewsets, mixins, permissions, status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.forms.models import model_to_dict
from rest_framework.decorators import action
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from openai import OpenAI
from django.db.models import Sum, F
from django.core.serializers import serialize
from django.utils.timezone import now
import json
from api.custom_permissions import IsTeacher

from api.models import Meeting, ClassMember, Remark, Rating, Feedback, MeetingComment, MeetingPresentor, User, SpringProjectBoard, SpringBoardTemplate, MeetingCriteria,SpringProject,Criteria, Feedback

from api.serializers import MeetingSerializer, MeetingCommentSerializer, MeetingCriteriaSerializer, MeetingPresentorSerializer, RatingSerializer, RemarkSerializer, FeedbackSerializer, NoneSerializer

VIDEOSDK_API_ENDPOINT=os.environ.get('VIDEOSDK_API_ENDPOINT')

class MeetingsController(viewsets.GenericViewSet,
                      mixins.ListModelMixin, 
                      mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.DestroyModelMixin):
    
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    authentication_classes = [JWTAuthentication]

    VIDEOSDK_API_KEY  = os.environ.get('VIDEOSDK_API_KEY')
    VIDEOSDK_SECRET_KEY = os.environ.get('VIDEOSDK_SECRET_KEY')

    def get_permissions(self):
        if self.action in ['create','destroy', 'update', 'partial_update','retrieve', 'list', 'join']:
        #     return [permissions.IsAuthenticated(), IsTeacher()]
        # elif self.action in []:
            return [permissions.IsAuthenticated()]

        return super().get_permissions()
    
    @swagger_auto_schema(
        operation_summary="List all meetings under a classroom.",
        operation_description="GET /meetings",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    def list(self, request):
        status_param = request.query_params.get('status', None)
        classroom_param = request.query_params.get('classroom', None)

        queryset = Meeting.objects.all()

        if classroom_param:
            queryset = queryset.filter(classroom_id=classroom_param)
            
        if status_param and status_param != "all":
            queryset = queryset.filter(status=status_param)

        serializer = MeetingSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Creates a new comment for the specific meeting.",
        operation_description="POST /meetings/{id}/comments",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingCommentSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def add_comment(self, request, *args, **kwargs):
        meeting = self.get_object()
        
        try:
            commentString = request.data['comment'] 
            classMemberId = request.data['classmember_id'] 
            # get ClassMember instance
            classMember = ClassMember.objects.get(id=classMemberId)

            comment = MeetingComment.objects.create(
                classmember_id=classMember,
                comment=commentString
              )

            comment_serializer = MeetingCommentSerializer(comment)
            meeting.comments.add(comment_serializer.data['id'])
            return Response(comment_serializer.data, status=status.HTTP_201_CREATED)

            # if comment_serializer.is_valid():
            # return Response(comment_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ClassMember.DoesNotExist:
            return Response({'details': 'Class member not found'}, status=status.HTTP_404_NOT_FOUND)
            
    @swagger_auto_schema(
        operation_summary="List comments for the specific meeting.",
        operation_description="GET /meetings/{id}/comments",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingCommentSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_comments(self, request, *args, **kwargs):
        meeting = self.get_object()

        comment_serializer = MeetingCommentSerializer(meeting.comments.all(), many=True)

        return Response(comment_serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="Add a new pitch as presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/presentors/",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def add_presentor(self, request, *args, **kwargs):
        meeting = self.get_object()

        request.data['meeting_id'] = meeting.id

        presentor_serializer = MeetingPresentorSerializer(data=request.data)

        if presentor_serializer.is_valid():
            presentor_serializer.save()
            meeting.presentors.add(presentor_serializer.data['id'])
            meeting.save()
            return Response(presentor_serializer.data, status=status.HTTP_201_CREATED)
        return Response(presentor_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    @swagger_auto_schema(
        operation_summary="List presentors for the specific meeting.",
        operation_description="GET /meetings/{id}/presentors/",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_presentors(self, request, *args, **kwargs):
        meeting = self.get_object()

        presentor_serializer = MeetingPresentorSerializer(meeting.presentors.all(), many=True)

        return Response(presentor_serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="Add a new criterias for the specific meeting.",
        operation_description="POST /meetings/{id}/criterias/",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingCriteriaSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def add_criteria(self, request, *args, **kwargs):
        meeting = self.get_object()

        request.data['meeting_id'] = meeting.id

        criteria_serializer = MeetingCriteriaSerializer(data=request.data)

        if criteria_serializer.is_valid():
            criteria_serializer.save()
            meeting.criterias.add(criteria_serializer.data['id'])
            meeting.save()
            return Response(criteria_serializer.data, status=status.HTTP_201_CREATED)
        return Response(criteria_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    @swagger_auto_schema(
        operation_summary="List criterias for the specific meeting.",
        operation_description="GET /meetings/{id}/criterias/",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_criterias(self, request, *args, **kwargs):
        meeting = self.get_object()

        meeting_criteria_id = MeetingCriteriaSerializer(meeting.criterias.all(), many=True)

        return Response(meeting_criteria_id.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="Update is_rate_open to true to the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/open_rating_to_pitch/",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', NoneSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def open_rating_to_pitch(self, request, *args, **kwargs):
        meeting = self.get_object()
        presentor = request.data.get('presentor')

        for p in MeetingPresentor.objects.filter(meeting_id=meeting.id):
            p.is_rate_open = False
            p.save()

        selected_presentor = meeting.presentors.get(id=presentor)

        selected_presentor.is_rate_open = True
        selected_presentor.save()

        return Response({'message': f'Rating is open for the selected presentor'}, status=status.HTTP_200_OK)


    @swagger_auto_schema(
        operation_summary="Add a score/rating to the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/add_rating_to_pitch/",
        request_body=RatingSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', RatingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def add_rating_to_pitch(self, request, *args, **kwargs):
        meeting = self.get_object()

        request.data['meeting_id'] = meeting.id

        rating_serializer = RatingSerializer(data=request.data)

        if rating_serializer.is_valid():
            rating_serializer.save()
            return Response(rating_serializer.data, status=status.HTTP_201_CREATED)
        print(rating_serializer.errors)
        return Response(rating_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="Update a score/rating to the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/update_rating_to_pitch/",
        request_body=RatingSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', RatingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['PUT'])
    def update_rating_to_pitch(self, request, *args, **kwargs):
        meeting = self.get_object()
        rating_id = request.data.get('id')
        pitch = request.data.get('pitch_id')
        new_rating = request.data.get('rating')
        meeting_criteria_id = request.data.get('meeting_criteria_id')

        rating= Rating.objects.get(id=rating_id)

        rating.rating = new_rating

        rating.save()

        return Response(RatingSerializer(rating).data, status=status.HTTP_200_OK)
    

    @swagger_auto_schema(
        operation_summary="Add a reamark to the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/add_remark_to_pitch/",
        request_body=RemarkSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', RemarkSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def add_remark_to_pitch(self, request, *args, **kwargs):
        meeting = self.get_object()

        request.data['meeting_id'] = meeting.id

        rating_serializer = RemarkSerializer(data=request.data)

        if rating_serializer.is_valid():
            rating_serializer.save()
            return Response(rating_serializer.data, status=status.HTTP_201_CREATED)
        return Response(rating_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="Update a remark to the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/update_remark_to_pitch/",
        request_body=RemarkSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', RemarkSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['PUT'])
    def update_remark_to_pitch(self, request, *args, **kwargs):
        meeting = self.get_object()

        pitch = request.data.get('pitch_id')
        new_remark = request.data.get('remark')

        remark= Remark.objects.get(meeting_id=meeting.id, pitch_id=pitch)

        remark.remark = new_remark

        remark.save()

        return Response(RemarkSerializer(remark).data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="Summarize the reamarks of the presentors for the specific meeting.",
        operation_description="POST /meetings/{id}/summarize_presentors_remarks/",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def summarize_presentors_remarks(self, request, *args, **kwargs):
        meeting = self.get_object()

        presentors = MeetingPresentorSerializer(meeting.presentors.all(), many=True).data
        print("Summarizing: ")

        for presentor in presentors:
            remarks = RemarkSerializer(Remark.objects.filter(meeting_id=meeting.id, pitch_id=presentor['pitch_id']), many=True).data    
            prompt = '\n\n'.join(remark['remark'] for remark in remarks if 'remark' in remark)

            complete_prompt = f'Please provide a concise summary of the remarks. Highlight key strengths and areas for improvement mentioned by each evaluator. Provide it into a single paragraph.{prompt}'

            client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))
            openai_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    'role': 'user', 'content': complete_prompt
                }],
                temperature=0
            )

            feedback = {
                'pitch_id': presentor['pitch_id'],
                'meeting_id': meeting.id,
                'feedback': openai_response.choices[0].message.content
            }
            print("Feedback Summary: " + openai_response.choices[0].message.content)
            feedback_serializer = FeedbackSerializer(data=feedback)

            if not feedback_serializer.is_valid():
                return Response(feedback_serializer.error_messages, status=status.HTTP_400_BAD_REQUEST)
    
            feedback_serializer.save()
            presentor['feedback'] = feedback_serializer.data

            return Response(presentors, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="List all of the rating to the presentors for the specific meeting.",
        operation_description="GET /meetings/{id}/rating_history/",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_rating_history(self, request, *args, **kwargs):
        meeting = self.get_object()

        ratings = Rating.objects.filter(meeting_id=meeting.id).select_related('classmember_id')

        serialized_ratings = RatingSerializer(ratings, many=True).data

        for rating in serialized_ratings:
            class_member = ratings.get(id=rating['id']).classmember_id
            rating['classmember'] = model_to_dict(class_member)

        return Response(serialized_ratings, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="List all of the remarks to the presentors for the specific meeting.",
        operation_description="GET /meetings/{id}/remark_history/",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_remark_history(self, request, *args, **kwargs):
        meeting = self.get_object()

        remarks = Remark.objects.filter(meeting_id=meeting.id)
        serializedRemarks = RemarkSerializer(remarks, many=True).data
        return Response(serializedRemarks, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="List all of the feedbacks to the presentors for the specific meeting.",
        operation_description="GET /meetings/{id}/feedback_history/",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingPresentorSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['GET'])
    def get_feedback_history(self, request, *args, **kwargs):
        meeting = self.get_object()

        feedbacks = Feedback.objects.filter(meeting_id=meeting.id)
        serializedFeedbacks = FeedbackSerializer(feedbacks, many=True).data
        return Response(serializedFeedbacks, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Start Meeting.",
        operation_description="POST /meetings/{id}/start_meeting",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def start_meeting(self, request, *args, **kwargs):
        meeting = self.get_object()

        meeting.status = "in_progress"

        # video sdk
        expiration_in_seconds = 600
        expiration = datetime.datetime.now() + datetime.timedelta(seconds=expiration_in_seconds)
        token = jwt.encode(payload={
            'exp': expiration,
            'apikey': self.VIDEOSDK_API_KEY,
            'permissions': ['allow_join', 'allow_mod'],
        }, key=self.VIDEOSDK_SECRET_KEY, algorithm="HS256")

        res = requests.post(f'{VIDEOSDK_API_ENDPOINT}/api/meetings',
                            headers={'Authorization': token})
        meeting.video = res.json()['meetingId']
        meeting.token = token
        meeting.save()

        meeting_data = MeetingSerializer(meeting).data

        meeting_data['token'] = token

        return Response(meeting_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Join Meeting.",
        operation_description="POST /meetings/{id}/join_meeting",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def join_meeting(self, request, *args, **kwargs):
        meeting = self.get_object()

        # video sdk
        expiration_in_seconds = 600
        expiration = datetime.datetime.now() + datetime.timedelta(seconds=expiration_in_seconds)
        token = jwt.encode(payload={
            'exp': expiration,
            'apikey': self.VIDEOSDK_API_KEY,
            'permissions': ['allow_join', 'allow_mod'],
        }, key=self.VIDEOSDK_SECRET_KEY, algorithm="HS256")

        # res = requests.post(f'{VIDEOSDK_API_ENDPOINT}/api/meetings/{meeting.video}',
        #                     headers={'Authorization': token})

        meeting_data = MeetingSerializer(meeting).data

        meeting_data['token'] = token

        return Response(meeting_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="End Meeting.",
        operation_description="PUT /meetings/{id}/end_meeting",
        request_body=NoneSerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def end_meeting(self, request, *args, **kwargs):
        meeting = self.get_object()

        meeting.status = "completed"
        meeting.video = None
        # meeting.save()~
        print("Complete Meeting: ")
        template_instance = SpringBoardTemplate.objects.filter(title = "Pitch").first()
        if not template_instance:
            template_instance = SpringBoardTemplate.objects.create(
                title="Pitch",
                content="",
                rules = "",
                description = "Project board for the result of the Pitching and Validation",
                date_created = now(),
                classroom = meeting.classroom_id
            )
        print(template_instance)
        meetingCriterias = MeetingCriteria.objects.filter(meeting_id = meeting.id)
        print(meetingCriterias)
        meetingPresentors = MeetingPresentor.objects.filter(meeting_id = meeting.id)
        print(meetingPresentors)

        for meetingPresentor in meetingPresentors:
            meeting = meetingPresentor.meeting_id
            pitch = meetingPresentor.pitch_id
            team = meetingPresentor.team_id

            criteria_feedback = {}
            total_score = 0
            num_criteria = 0

            for criteria in meetingCriterias:
                print("criteria_id")
                print(criteria)
                ratings = Rating.objects.filter(meeting_id = meeting.id, pitch_id = pitch)
                print("rating:")
                print(ratings)
                print("meeting_id:")
                print(meeting.id)
                print("pitch:")
                print(pitch)
                print("meeting_criteria_id:")
                print(criteria.criteria_id.name)

                overall_score = 0
                print("overall_score")
                print(overall_score)
                teacher_score = 0
                student_score = 0
                guest_score = 0
                teacher_count = 0
                student_count = 0
                guest_count = 0
                for rating in ratings:                    
                    role = rating.classmember_id.role
                    print("role:")
                    print(rating.classmember_id.role)
                    
                    if role == 0:  # Teacher
                        member_role_weight = meeting.teacher_weight_score
                        teacher_score += rating.rating * member_role_weight * criteria.weight
                        teacher_count += 1
                    elif role == 1:  # Student
                        member_role_weight = meeting.student_weight_score
                        student_score += rating.rating * member_role_weight * criteria.weight
                        student_count += 1
                    elif role == 2:  # Guest
                        member_role_weight = meeting.guest_weight_score
                        guest_score += rating.rating * member_role_weight * criteria.weight
                        guest_count += 1

                    print("weight score:")
                    print(member_role_weight)
                    print("teacher_count:")
                    print(teacher_count)
                    print("student_count:")
                    print(student_count)
                    print("guest_count:")
                    print(guest_count)
                teacher_ave = teacher_score / teacher_count if teacher_count != 0 else 0
                student_ave = student_score / student_count if student_count != 0 else 0
                guest_ave = guest_score / guest_count if guest_count != 0 else 0
                overall_score = teacher_ave + student_ave + guest_ave
                
                print("teacher_ave")
                print(teacher_ave)
                print("student_ave")
                print(student_ave)
                print("guest_ave")
                print(guest_ave)
                print("overall_score")
                print(overall_score)
                criteria_json_entry = {
                    "score": round(overall_score*2),
                    "description": criteria.criteria_id.description
                }
                criteria_feedback[criteria.criteria_id.name] = criteria_json_entry
                print(criteria_json_entry)
                total_score += overall_score
                num_criteria += 1  # Increment the criteria count

            average_score = round((total_score / num_criteria) * 2) if num_criteria != 0 else 0
            print("boardscore: " )
            print(average_score)
            criteria_json_string = json.dumps(criteria_feedback, indent=4)
            print(criteria_json_string)
            spring_project = SpringProject.objects.filter(team_id=team.id, is_active=True).first()
            spring_projectboard = SpringProjectBoard.objects.filter(project_id=spring_project, title = "Pitch").first()
            feedback = Feedback.objects.filter(meeting_id = meeting.id, pitch_id = pitch.id).first()
            print("meeting_id: ")
            print(meeting.id)
            print("pitch_id: " )
            print(pitch.id)
            print("Feedback: ")
            feedback_text = feedback.feedback if feedback else ""
            print(feedback_text)
            if not spring_projectboard:
                spring_projectboard = SpringProjectBoard.objects.create(
                title= template_instance.title,
                template_id=template_instance.id,
                feedback=feedback_text,
                recommendation="",
                references="",
                project_id=spring_project,
                criteria_feedback=criteria_json_string,
                score=average_score,
                )
                spring_project.score = (spring_projectboard.score + int(average_score))/2
                print("Created New")
            else:
                spring_project.score -= spring_projectboard.score
                spring_project.score += int(average_score)
                
                spring_projectboard.feedback = feedback_text
                spring_projectboard.score = average_score
                spring_projectboard.criteria_feedback = criteria_json_string
                
            spring_projectboard.save()
            spring_project.save()
            
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_200_OK)

    swagger_auto_schema(
        operation_summary="Invite User to Meeting.",
        operation_description="POST /meetings/{id}/invite",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=True, methods=['POST'])
    def invite(self, request, *args, **kwargs):
        meeting = self.get_object()
        email = request.data.get('email')
        
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            meeting.invited_users.add(user)
            meeting.save()
            return Response({"message": f"{email} invited successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    swagger_auto_schema(
        operation_summary="Get Invited Meetings.",
        operation_description="GET /meetings/get_invited_meetings/{email}",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=False, methods=['GET'])
    def get_invited_meetings(self, request):
        email = request.query_params.get('email')  
        if not email:
            return Response({"error": "Email parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        #Get meetings where the user is an invited participant
        meetings = Meeting.objects.filter(invited_users=user).exclude(status='completed')

        if not meetings.exists():
            return Response({"message": "No meetings found for this user."}, status=status.HTTP_404_NOT_FOUND)

        #Collect meeting IDs and statuses
        #Can modify this and add more important values to be returned
        #This is the current return, id and classroom_id is needed to join a meeting.
        meeting_data = meetings.values('id', 'status', 'classroom_id', 'name')

        return Response({"meetings": list(meeting_data)}, status=status.HTTP_200_OK)

    swagger_auto_schema(
        operation_summary="Validate User Email Invite.",
        operation_description="POST /meetings/validate_email",
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', MeetingSerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    @action(detail=False, methods=['POST'])
    def validate_email(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        exists = User.objects.filter(email=email).exists()
        if exists:
            return Response({"message": "Email exists"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Email not found"}, status=status.HTTP_404_NOT_FOUND)