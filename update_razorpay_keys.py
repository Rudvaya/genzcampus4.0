from app import app
from models import db, SystemConfig

def update_keys():
    with app.app_context():
        # Update Key ID
        key_id = SystemConfig.query.filter_by(key='razorpay_key_id').first()
        if key_id:
            key_id.value = 'rzp_test_SXw5U2Fsta3kkG'
        else:
            db.session.add(SystemConfig(key='razorpay_key_id', value='rzp_test_SXw5U2Fsta3kkG'))
            
        # Update Key Secret
        key_secret = SystemConfig.query.filter_by(key='razorpay_key_secret').first()
        if key_secret:
            key_secret.value = 'WaRLf3OkfolhaMovjMYvk1Zk'
        else:
            db.session.add(SystemConfig(key='razorpay_key_secret', value='WaRLf3OkfolhaMovjMYvk1Zk'))
            
        db.session.commit()
        print("Razorpay Test Keys updated successfully in database.")

if __name__ == '__main__':
    update_keys()
