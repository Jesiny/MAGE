# coding: utf-8
'''
    @license: Apache License, Version 2.0
    @copyright: 2007-2013 Marc-Antoine Gouillart
    @author: Marc-Antoine Gouillart
'''

## Python imports
from UserDict import DictMixin
import inspect

## Django imports
from django.db import models
from django.db.models.base import ModelBase
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

## MAGE imports
from MAGE.exceptions import MageError


################################################################################
## Helpers
################################################################################

class SLA(models.Model):
    rto = models.IntegerField()
    rpo = models.IntegerField()
    avalability = models.FloatField()
    #closed =
    open_at = models.TimeField()
    closes_at = models.TimeField()
    
    class Meta:
        verbose_name = 'SLA'
        verbose_name_plural = 'SLA'  
    
     
################################################################################
## Classifiers
################################################################################

class Project(models.Model):
    """ 
        referential objects may optionally be classified inside projects, defined by a code name
        and containing a description
    """
    name = models.CharField(max_length=100, unique=True)
    alternate_name_1 = models.CharField(max_length=100, null=True, blank=True)
    alternate_name_2 = models.CharField(max_length=100, null=True, blank=True)
    alternate_name_3 = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=500)
    default_convention = models.ForeignKey('Convention', null=True, blank=True, related_name='used_in_projects')
    
    class Meta:
        verbose_name = u'projet'
        verbose_name_plural = u'projets'
        
    def __unicode__(self):
        return self.name

class Application(models.Model):
    name = models.CharField(max_length=100, unique=True)
    alternate_name_1 = models.CharField(max_length=100, null=True, blank=True)
    alternate_name_2 = models.CharField(max_length=100, null=True, blank=True)
    alternate_name_3 = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=500)
    project = models.ForeignKey(Project, null=True, blank=True, related_name='applications')
    
    def __unicode__(self):
        return self.name
    
    
################################################################################
## Constraints on environment instantiation
################################################################################
    
class LogicalComponent(models.Model):
    name = models.CharField(max_length=100, verbose_name='nom')
    description = models.CharField(max_length=500)
    application = models.ForeignKey(Application)
    scm_trackable = models.BooleanField(default=True)
    active = models.BooleanField(default=True, verbose_name=u'utilisé')
    ref1 = models.CharField(max_length=20, verbose_name=u'reférence 1', blank=True, null=True)
    ref2 = models.CharField(max_length=20, verbose_name=u'reférence 2', blank=True, null=True)
    ref3 = models.CharField(max_length=20, verbose_name=u'reférence 3', blank=True, null=True)
    
    def __unicode__(self):
        return u'%s' % (self.name)
    
    class Meta:
        verbose_name = u'composant logique'
        verbose_name_plural = u'composants logiques'
    
class ComponentImplementationClass(models.Model):
    """ An implementation offer for a given service. """
    name = models.CharField(max_length=100, verbose_name='code')
    
    description = models.CharField(max_length=500)
    implements = models.ForeignKey(LogicalComponent, related_name='implemented_by', verbose_name=u'composant logique implémenté')
    sla = models.ForeignKey(SLA, blank=True, null=True)
    technical_description = models.ForeignKey('ImplementationDescription', related_name='cic_set', verbose_name=u'description technique')
    ref1 = models.CharField(max_length=20, verbose_name=u'reférence 1', blank=True, null=True)
    ref2 = models.CharField(max_length=20, verbose_name=u'reférence 2', blank=True, null=True)
    ref3 = models.CharField(max_length=20, verbose_name=u'reférence 3', blank=True, null=True)
    active = models.BooleanField(default=True, verbose_name=u'utilisé')
    
    def __unicode__(self):
        return u'%s' % self.name
    
    class Meta:
        verbose_name = u'déclinaison technique d\'un CL'
        verbose_name_plural = u'déclinaisons techniques des CL'

class EnvironmentType(models.Model):
    """ The way logical components are instanciated"""
    name = models.CharField(max_length=100, verbose_name='Nom')
    description = models.CharField(max_length=500, verbose_name='description')
    short_name = models.CharField(max_length=10, verbose_name='code')
    sla = models.ForeignKey(SLA, blank=True, null=True)
    implementation_patterns = models.ManyToManyField(ComponentImplementationClass, blank=True)
    chronological_order = models.IntegerField(default=1, verbose_name='ordre d\'affichage')
    default_convention = models.ForeignKey('Convention', null=True, blank=True, related_name='used_in_envt_types')
    default_show_sensitive_data = models.BooleanField(default=False, verbose_name="afficher les informations sensibles")
    
    def __get_cic_list(self):
        return ','.join([ i.name for i in self.implementation_patterns.all()])
    cic_list = property(__get_cic_list)
    
    def __unicode__(self):
        return self.name


################################################################################
## Description of the component instances
################################################################################

def _resolve(pattern, instance):
    ''' Will instanciate a pattern according to the value inside the given component instance'''
    res = u""
    for segment in pattern.split("|"):
        seg_res = ""
        if segment[0] == "%": 
            segment = segment[1:]           
            for sub_prio_segment in segment.split(";"):
                seg_res = instance
                for field in sub_prio_segment.split("."):
                    if isinstance(seg_res, ComponentInstance):
                        seg_res = seg_res.proxy 
                    seg_res = seg_res.__getattribute__(field)
                    if seg_res is None:
                        ## Go to next priority segment - this one is None
                        break
                else:
                    ## If here: a priority segment was completely computed (no break)
                    if seg_res:
                        ## If the result is not None, no need to go over the lower-priority segments.
                        break 
        else:
            # simple segment - directly return the content, no resolution required
            seg_res = segment
        
        res += seg_res
    
    return res
        
class ImplementationRelationType(models.Model):
    name = models.CharField(max_length=20, verbose_name='type relation')  
    label = models.CharField(max_length=100, verbose_name='label')
    
    def __unicode__(self):
        return self.name  
        
class ImplementationFieldDescription(models.Model):
    """ The description of a standard (i.e. that must be completed by the user) field inside a technical implementation """
    name = models.CharField(max_length=100, verbose_name='Nom du champ')
    default = models.CharField(max_length=500, verbose_name='défaut', null=True, blank=True)
    datatype = models.CharField(max_length=20, default='str', choices=(('str', 'chaîne de caractères'), ('int', 'entier')), verbose_name=u'type')
    label = models.CharField(max_length=100, verbose_name='label')
    sensitive = models.BooleanField(default=False, verbose_name='sensible')
    
    implementation = models.ForeignKey('ImplementationDescription', related_name='field_set', verbose_name=u'implémentation mère')
    
    def __unicode__(self):
        return '%s (%s)' % (self.name, self.implementation.name)
    
    class Meta:
        verbose_name = u'champ simple'
        verbose_name_plural = u'champs simples'

class ImplementationComputedFieldDescription(models.Model):
    """ The description of a calculated field inside a technical implementation """
    name = models.CharField(max_length=100, verbose_name='Nom du champ')
    pattern = models.CharField(max_length=500, verbose_name='chaîne de calcul')   
    label = models.CharField(max_length=100, verbose_name='label')
    sensitive = models.BooleanField(default=False, verbose_name='sensible')
    
    implementation = models.ForeignKey('ImplementationDescription', verbose_name=u'implémentation mère', related_name='computed_field_set')
    
    def __unicode__(self):
        return '%s' % (self.name)
    
    def resolve(self, instance):
        return _resolve(self.pattern, instance)
    
    class Meta:
        verbose_name = u'champ calculé'
        verbose_name_plural = u'champs calculés'
        
class ImplementationRelationDescription(models.Model):
    name = models.CharField(max_length=100, verbose_name='Nom du champ')
    label = models.CharField(max_length=100, verbose_name='label')   
    source = models.ForeignKey('ImplementationDescription', related_name='target_set', verbose_name='type source')
    target = models.ForeignKey('ImplementationDescription', related_name='is_targeted_by_set', verbose_name=u'type cible')
    min_cardinality = models.IntegerField(default=0)
    max_cardinality = models.IntegerField(blank=True, null=True)
    link_type = models.ForeignKey(ImplementationRelationType)
    
    def __unicode__(self):
        return '%s (%s)' % (self.name, self.source.name)
    
    class Meta:
        verbose_name = u'relation'
        verbose_name_plural = u'relations'

class ProxyRelSequence:
    '''
        Sequence type for handling relationships inside a proxy instance object.
        Some sequence methods are not implemented: 
            __setitem__: cannot change link - only add/delete links
            insert: relationships are not ordered, so no need to insert at specific position
            sort: see above
            reverse: see above
    '''
    
    def __init__(self, proxy, rel_descr):
        self.proxy = proxy
        self.rel_descr = rel_descr
    
    def __djangoseq__(self):
        return [i.target for i in ComponentInstanceRelation.objects.select_related('target').filter(source=self.proxy._instance, field=self.rel_descr).order_by('id')]
    
    def __delitem__(self, key):
        ''' for deletion of self[key]'''
        self.remove(self[key])
    
    def __getitem__(self, key):
        return self.__djangoseq__().__getitem__(key)
    
    def __iter__(self):
        return self.__djangoseq__().__iter__()
        
    def __len__(self):
        return len(self.__djangoseq__())
    
    def __str__(self):
        return self.__djangoseq__().__str__()
    
    def __eq__(self, other_seq):
        return other_seq.proxy._instance._id == self.proxy._instance.id and self.rel_descr.id == other_seq.rel_descr.id
    
    def __contains__(self, instance):
        return ComponentInstanceRelation.objects.filter(source=self.proxy._instance, target=instance if isinstance(instance, ComponentInstance) else instance._instance, field=self.rel_descr).count() > 0
    
    def append(self, target_instance):
        r = ComponentInstanceRelation(source=self.proxy._instance, target=target_instance if isinstance(target_instance, ComponentInstance) else target_instance._instance, field=self.rel_descr)
        r.save()
        
    def count(self, instance):
        return ComponentInstanceRelation.objects.select_related('target').filter(source=self.proxy._instance, target=instance, field=self.rel_descr).count()
        
    def index(self, instance):
        return self.__djangoseq__().index(instance if isinstance(instance, ComponentInstance) else instance._instance)
    
    def extend(self, instance_list):
        for item in instance_list:
            self.append(item)
    
    def pop(self, i=None):
        if not i:
            i = self.__len__() - 1
        rel_instance = ComponentInstanceRelation.objects.select_related('target').filter(source=self.proxy._instance, field=self.rel_descr).order_by('id')[i] 
        item = rel_instance.target
        rel_instance.delete()
        return item
    
    def remove(self, target_instance):
        ComponentInstanceRelation.objects.filter(source=self.proxy._instance, target=target_instance if isinstance(target_instance, ComponentInstance) else target_instance._instance, field=self.rel_descr).delete() 
    
        
def _proxyinit(self, base_instance=None, _cic=None, _env=None, **kwargs):
    if not base_instance is None:
        self._instance = base_instance
    elif not self.__class__._related_impl is None:
        self._instance = ComponentInstance(implementation=self.__class__._related_impl)
        self._instance.save()
        
        for field in self.__class__._related_impl.field_set.filter(default__isnull=False):
            setattr(self, field.name, field.default)
        
        for name, value in kwargs.items():
            setattr(self, name, value)
    
    ## Logical component (through CIC): either a CIC is given as an object, as a string or there is just no choice. 
    if _cic and isinstance(_cic, ComponentImplementationClass):
        self._instance.instanciates = _cic
    elif _cic and isinstance(_cic, str):
        self._instance.instanciates = ComponentImplementationClass.objects.get(name=_cic)
    elif self.__class__._related_impl and self.__class__._related_impl.cic_set.count() == 1:
        self._instance.instanciates = self.__class__._related_impl.cic_set.all()[0]
        
    ## Envts
    if _env and type(_env) is list:
        for env in _env:
            self._instance.environments.add(env)
    elif _env and type(_env) is str:
        self._instance.environments.add(Environment.objects.get(name=_env))
    elif _env and type(_env) is Environment:
        self._instance.environments.add(_env)
        
    ## helper accessor to extended parameters
    self.extended_parameters = ExtendedParameterDict(self._instance)
    
_classes = {}            
class ImplementationDescription(models.Model):
    """ The description of a technical implementation """
    name = models.CharField(max_length=100, verbose_name='nom')
    description = models.CharField(max_length=500, verbose_name='description')
    tag = models.CharField(max_length=100, verbose_name=u'étiquette libre', null=True, blank=True)
    relationships = models.ManyToManyField('ImplementationDescription', through=ImplementationRelationDescription)
    include_in_default_envt_backup = models.BooleanField(default=False, verbose_name=u'inclure dans les backups par défaut')
    self_description_pattern = models.CharField(max_length=500, verbose_name='motif d\'auto description', help_text=u'sera utilisé pour toutes les descriptions par défaut des instances de composant. Utilise les même motifs (patterns) que les champs dynamiques.')
    
    def __unicode__(self):
        return self.name
    
    def resolve_self_description(self, instance):
        return _resolve(self.self_description_pattern, instance)
    
    class Meta:
        verbose_name = u'paramétres d\'implémentation'
        verbose_name_plural = u'paramétres des implémentations'
        
    def proxy_class(self):        
        try:
            return _classes[self.name]
        except:
            #TODO: datatype!
            attrs = {'__init__': _proxyinit, 'save': lambda slf: slf._instance.save()}
            
            ## Standard fields
            for field in self.field_set.all():            
                getter = lambda slf, field_id = field.id: slf._instance.field_set.get(field_id=field_id).value if slf._instance.field_set.get_or_none(field_id=field_id) else None 
                setter = lambda slf, value, lfield = field: ComponentInstanceField.objects.update_or_create(defaults={'value': value} , field=lfield, instance=slf._instance)
                attrs[field.name] = property(fget=getter, fset=setter, doc=field.label)
                
            ## Self to others relationships
            for field in self.target_set.all():
                if not field.max_cardinality or field.max_cardinality > 1:
                    ## In this case, list manipulation through a proxy object
                    getter = lambda slf, field = field: ProxyRelSequence(proxy=slf, rel_descr=field)
                else:
                    ## Direct get/set on a field
                    getter = lambda slf, field_id = field.id: slf._instance.rel_target_set.get(field_id=field_id).target
                    setter = lambda slf, value, field_id = field.id:  ComponentInstanceRelation.objects.update_or_create(defaults={'target': value._instance if value._instance else value}, source=slf._instance, field_id=field_id)
                attrs[field.name] = property(fget=getter, fset=setter, doc=field.label) 
              
            ## Other to self relationships
            #...
            
            ## Computed fields (read only)
            for field in self.computed_field_set.all():         
                getter = lambda slf, pfield = field: pfield.resolve(slf) 
                attrs[field.name] = property(fget=getter, doc=field.label)            
            
            ## Create the class  
            cls = type(str("__" + self.name.lower() + "_proxy"), (), attrs)
            cls._related_impl = self
            _classes[self.name] = cls
            return cls
        
    @staticmethod
    def class_for_name(name):
        descr = ImplementationDescription.objects.get(name=name)
        return descr.proxy_class()
    
    @staticmethod
    def create_or_update(name, description, self_description_pattern, tag=None, include_in_default_envt_backup=False):
        try:
            idn = ImplementationDescription.objects.get(name=name)
            idn.description = description
            idn.self_description_pattern = self_description_pattern
            idn.tag = tag
            idn.include_in_default_envt_backup = include_in_default_envt_backup
            idn.save()
            return idn
        except:
            idn = ImplementationDescription(name=name, description=description, self_description_pattern=self_description_pattern, tag=tag, include_in_default_envt_backup=include_in_default_envt_backup)
            idn.save()
            return idn
    
    def add_field_simple(self, name, label, default=None, sensitive=False, datatype='str'):
        self.field_set.add(ImplementationFieldDescription(name=name, label=label, sensitive=sensitive, datatype=datatype, default=default, implementation=self))
        return self
    
    def add_field_computed(self, name, label, pattern, sensitive=False):
        self.computed_field_set.add(ImplementationComputedFieldDescription(name=name, label=label, pattern=pattern, sensitive=sensitive, implementation=self))
        return self
    
    def add_relationship(self, name, label, target, link_type, min_cardinality=0, max_cardinality=1):
        self.target_set.add(ImplementationRelationDescription(name=name, label=label, source=self, target=target, min_cardinality=min_cardinality, max_cardinality=max_cardinality, link_type=link_type))    
        return self
    
    
################################################################################
## Main notion: the environment
################################################################################

class EnvironmentManagerStd(models.Manager):
    def get_queryset(self):
        return super(EnvironmentManagerStd, self).get_query_set().filter(template_only=False, active=True)
    
class Environment(models.Model):
    """ 
        A set of components forms an environment
    """
    name = models.CharField(max_length=100, verbose_name='Nom')
    buildDate = models.DateField(verbose_name=u'Date de création', auto_now_add=True)
    destructionDate = models.DateField(verbose_name=u'Date de suppression prévue', null=True, blank=True)
    description = models.CharField(max_length=500)
    manager = models.CharField(max_length=100, verbose_name='responsable', null=True, blank=True)
    project = models.ForeignKey(Project, null=True, blank=True)
    typology = models.ForeignKey(EnvironmentType)
    template_only = models.BooleanField(default=False)
    active = models.BooleanField(default=True, verbose_name=u'utilisé')
    show_sensitive_data = models.NullBooleanField(verbose_name="afficher les informations sensibles", null=True, blank=True)
    managed = models.BooleanField(default=True, verbose_name=u'administré')
    
    def __protected(self):
        if self.show_sensitive_data is not None:
            return not self.show_sensitive_data
        elif self.typology is not None:
            return not self.typology.default_show_sensitive_data
        else:
            return True
    protected = property(__protected)
    
    def __unicode__(self):
        return "%s" % (self.name,)
    
    objects = models.Manager()
    objects_active = EnvironmentManagerStd()
    
    class Meta:
        verbose_name = 'environnement'
        verbose_name_plural = 'environnements'  
    

################################################################################
## Environment components (actual instances of technical items)
################################################################################    

class RichManager(models.Manager):
    """ Standard manager with a few helper methods"""
    def get_or_none(self, *args, **kwargs):
        try:
            return self.get(*args, **kwargs)
        except self.model.DoesNotExist:
            return None

class ComponentInstanceRelation(models.Model):        
    source = models.ForeignKey('ComponentInstance', related_name='rel_target_set', verbose_name='instance source')
    target = models.ForeignKey('ComponentInstance', related_name='rel_targeted_by_set', verbose_name='instance cible')
    field = models.ForeignKey(ImplementationRelationDescription, verbose_name=u'champ implémenté', related_name='field_set')
    
    class Meta:
        verbose_name = u'valeur de relation'
        verbose_name_plural = u'valeurs des relations'
        
    def __unicode__(self):
        return 'valeur de %s' % self.field.name
    
class ComponentInstanceField(models.Model):
    objects = RichManager()
    
    value = models.CharField(max_length=255, verbose_name='valeur')
    field = models.ForeignKey(ImplementationFieldDescription, verbose_name=u'champ implémenté')
    instance = models.ForeignKey('ComponentInstance', verbose_name=u'instance de composant', related_name='field_set')
    
    class Meta:
        verbose_name = u'valeur de champ'
        verbose_name_plural = u'valeurs des champs'
        
    def __unicode__(self):
        return 'valeur de %s' % self.field.name
        
class ComponentInstance(models.Model):
    """Instances! Usually used through its proxy object"""    
        
    ## Base data for all components
    instanciates = models.ForeignKey(ComponentImplementationClass, null=True, blank=True, verbose_name=u'implémentation de ', related_name='instances')
    implementation = models.ForeignKey(ImplementationDescription, related_name='instance_set', verbose_name=u'décrit par l\'implémentation')
    deleted = models.BooleanField(default=False)
    include_in_envt_backup = models.BooleanField(default=False)
    
    ## Environments
    environments = models.ManyToManyField(Environment, blank=True, null=True, verbose_name='environnements ', related_name='component_instances')
    
    ## Connections
    #TODO: symmetrical
    relationships = models.ManyToManyField('self', verbose_name='relations', through=ComponentInstanceRelation, symmetrical=False, related_name='reverse_relationships')
    
    ## Proxy object for easier handling
    __proxy = None     
    def build_proxy(self, force=False):
        if self.implementation is None:
            return
        if self.__proxy is None or force:
            self.__proxy = self.implementation.proxy_class()(base_instance=self)
        return self.__proxy     
    proxy = property(build_proxy)
    
    ## Introspection helpers
    def exportable_fields(self, restricted_access=False):
        internal_attrs = ('latest_cic', 'leaf', 'pk', 'version', 'version_object_safe', 'default_convention')
        self.leaf.__dict__['component_type'] = self.model.model
        self.leaf.__dict__['lc_id'] = self.instanciates.implements.pk if self.instanciates else None
        if restricted_access:
            keys = self.leaf.__dict__.keys()
            for t in inspect.getmembers(type(self.leaf), lambda x: isinstance(x, property)):
                if t[0] in internal_attrs:
                    continue
                keys.append(t[0])
        else:      
            keys = [ i for i in self.leaf.__dict__.keys() if i not in self.leaf.restricted_fields]
            for t in inspect.getmembers(type(self.leaf), lambda x: isinstance(x, property)):
                if t[0] in internal_attrs or t[0] in self.leaf.restricted_fields:
                    continue
                keys.append(t[0])
        keys.remove('model_id');keys.remove('_state');keys.remove('componentinstance_ptr_id');keys.append('environments')
        return keys
            
    ## First environment
    def first_environment(self):
        if self.environments.count() > 0:
            return self.environments.all()[0]
        return None
    first_environment.short_description = u'notamment dans'
    
    ## Pretty print
    def __unicode__(self):
        if self.implementation:
            return self.implementation.resolve_self_description(self)
        else:
            return '%s' % self.pk
    name = property(__unicode__)

    class Meta:
        permissions = (('allfields_componentinstance', 'access all fields including restricted ones'),)
        verbose_name = 'instance de composant'
        verbose_name_plural = 'instances de composant'


class ExtendedParameterDict(DictMixin):
    def __init__(self, instance):
        self.instance = instance
    
    def __len__(self):
        return self.instance.parameter_set.all().count()
        
    def __getitem__(self, key): 
        try:
            return self.instance.parameter_set.get(key=key).value
        except ExtendedParameter.DoesNotExist:
            raise KeyError
    
    def __setitem__(self, key, value):
        ExtendedParameter.objects.update_or_create(defaults={'value': value}, key=key, instance=self.instance)        
    
    def __delitem__(self, key):
        ep = self.__getitem__(key)
        ep.delete()
        
    def keys(self):
        return self.instance.parameter_set.values_list('key', flat=True)
    
    def values(self):
        return self.instance.parameter_set.values_list('value', flat=True)

class ExtendedParameter(models.Model):
    key = models.CharField(max_length=50, verbose_name='clef')
    value = models.CharField(max_length=100, verbose_name='valeur')
    instance = models.ForeignKey(ComponentInstance, related_name='parameter_set')
    
    def __unicode__(self):
        return '%s on %s' % (self.key, self.instance.name)
    
    class Meta:
        verbose_name = u'paramètre étendu'
        verbose_name_plural = u'paramètres étendus'
    
    
################################################################################
## Naming and linking norms
################################################################################ 

class Convention(models.Model):
    name = models.CharField(max_length=20)
    
    def __unicode__(self):
        return u'Norme %s' % self.name
    
    class Meta:
        verbose_name = 'norme'
        verbose_name_plural = 'normes'
    
    def set_field(self, model_name, field_name, pattern):
        rel = self.fields.get(model=model_name, field=field_name)
        rel.pattern = pattern
        rel.save()
    
    # def value_field() # actually monkey patched from naming.py to avoid circular imports between mcl.py and models.py
    
class ConventionField(models.Model):
    model = models.CharField(max_length=254, verbose_name=u'composant technique')
    field = models.CharField(max_length=254, verbose_name=u'champ')
    pattern = models.CharField(max_length=1023, null=True, blank=True, verbose_name=u'norme') 
    convention_set = models.ForeignKey(Convention, related_name='fields') 
    pattern_type = models.CharField(max_length=4, choices=(('MCL1', 'MCL query with only one result'),
                                                               ('MCL0', 'MCL query with 0 to * results'),
                                                               ('P', 'simple pattern'),
                                                               ('CIC', 'implementation class name'),
                                                               ('TF', 'True ou False')))
    overwrite_copy = models.BooleanField(default=False, verbose_name=u'prioritaire sur copie')
    
    class Meta:
        verbose_name = u'norme de remplissage d\'un champ'
        verbose_name_plural = u'normes de remplissage des champs'
        
    def __unicode__(self):
        return u'%s.%s = %s' % (self.model, self.field, self.pattern)

class ConventionCounter(models.Model):
    scope_type = models.CharField(max_length=50)
    scope_param_1 = models.CharField(max_length=50, blank=True, null=True, default=None)
    scope_param_2 = models.CharField(max_length=50, blank=True, null=True, default=None)
    val = models.IntegerField(default=0, verbose_name='valeur actuelle')
    
    class Meta:
        verbose_name = u'Compteur'
     
