from users.models import Complaint
complaints = Complaint.objects.all()[:2]
if len(complaints) >= 2:
    complaints[0].location = 'Mumbai, India'
    complaints[0].save()
    complaints[1].location = 'Delhi, India'
    complaints[1].save()
    print('Updated locations for two complaints')
else:
    print('Not enough complaints')