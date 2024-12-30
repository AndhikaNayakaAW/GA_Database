#red/forms.py
from django import forms
from .models import Transaction

TRANSACTION_TYPE_CHOICES = [
    ('topup', 'Top-Up'),
    ('service_payment', 'Service Payment'),
    ('transfer', 'Transfer'),
    ('withdrawal', 'Withdrawal'),
]

class MyPayTransactionForm(forms.ModelForm):
    transaction_type = forms.ChoiceField(choices=TRANSACTION_TYPE_CHOICES, required=True, label="Transaction Type")
    
    class Meta:
        model = Transaction
        fields = ['amount', 'recipient', 'transaction_type', 'bank_name', 'bank_account']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide fields based on transaction type
        self.fields['recipient'].widget.attrs['style'] = 'display:none;'
        self.fields['bank_name'].widget.attrs['style'] = 'display:none;'
        self.fields['bank_account'].widget.attrs['style'] = 'display:none;'
        
        # Adjust visible fields dynamically
        if self.data.get('transaction_type') == 'transfer':
            self.fields['recipient'].widget.attrs.pop('style', None)
        elif self.data.get('transaction_type') == 'withdrawal':
            self.fields['bank_name'].widget.attrs.pop('style', None)
            self.fields['bank_account'].widget.attrs.pop('style', None)
