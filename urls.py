from django.urls import path
from . import views

urlpatterns = [
                path('', views.index, name='index'),
                path('datasource/', views.source_info, name='source_info'),
                path('statistics/', views.statistics, name='statistics'),
                path('statedata/<str:state_id>/', views.state, name='state'),
              ]

